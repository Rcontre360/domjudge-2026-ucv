import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as autoscaling from 'aws-cdk-lib/aws-autoscaling';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as fs from 'fs';
import * as path from 'path';

export class InfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const sshPublicKey = this.node.tryGetContext('sshPublicKey') as string;
    if (!sshPublicKey) {
      throw new Error('sshPublicKey context is required. Add it to cdk.json under "context".');
    }

    // 1. Use the default VPC — no need for a custom one for a single public instance
    const vpc = ec2.Vpc.fromLookup(this, 'DefaultVpc', { isDefault: true });

    // 2. Persistent EBS Volume (Standalone) — RETAIN keeps data even if stack is deleted
    const volume = new ec2.Volume(this, 'DomjudgeDataVolume', {
      availabilityZone: vpc.availabilityZones[0],
      size: cdk.Size.gibibytes(20),
      volumeType: ec2.EbsDeviceVolumeType.GP3,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // 3. Static IP (Elastic IP)
    const eip = new ec2.CfnEIP(this, 'DomjudgeEIP');

    // 4. SSH Key Pair — imported from the public key provided via context
    const keyPair = new ec2.KeyPair(this, 'DomjudgeKeyPair', {
      publicKeyMaterial: sshPublicKey,
    });

    // 5. Security Group — SSH is restricted to key-based auth via the key pair above
    const securityGroup = new ec2.SecurityGroup(this, 'DomjudgeSG', {
      vpc,
      allowAllOutbound: true,
    });
    securityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80), 'HTTP from CloudFront');
    securityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(22), 'SSH key-only');

    // 6. Auto Scaling Group (min=max=1 gives auto-restart without scaling)
    const asg = new autoscaling.AutoScalingGroup(this, 'DomjudgeASG', {
      vpc,
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
      machineImage: ec2.MachineImage.fromSsmParameter(
        '/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id',
        { os: ec2.OperatingSystemType.LINUX },
      ),
      minCapacity: 1,
      maxCapacity: 1,
      securityGroup,
      keyPair,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
    });

    // 7. Permissions for the instance to re-attach its own IP and volume on restart
    asg.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'ec2:AttachVolume',
        'ec2:DescribeVolumes',
        'ec2:AssociateAddress',
      ],
      resources: ['*'],
    }));

    // 8. UserData: inject CDK-resolved values then run the shared script
    const userDataLines = fs.readFileSync(path.join(__dirname, 'user-data.sh'), 'utf-8').split('\n');

    asg.addUserData(
      `export VOLUME_ID="${volume.volumeId}"`,
      `export ALLOCATION_ID="${eip.ref}"`,
      `export AWS_REGION="${this.region}"`,
      ...userDataLines,
    );

    // 9. CloudFront for HTTPS termination — no caching, forwards all headers for sessions
    const cf = new cloudfront.Distribution(this, 'DomjudgeProxy', {
      defaultBehavior: {
        origin: new origins.HttpOrigin(eip.attrPublicIp),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER,
      },
    });

    new cdk.CfnOutput(this, 'StaticIP', { value: eip.attrPublicIp });
    new cdk.CfnOutput(this, 'HttpsUrl', { value: `https://${cf.distributionDomainName}` });
  }
}
