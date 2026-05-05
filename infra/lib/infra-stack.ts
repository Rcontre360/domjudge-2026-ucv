import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as autoscaling from 'aws-cdk-lib/aws-autoscaling';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as iam from 'aws-cdk-lib/aws-iam';

export class InfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // 1. VPC restricted to 1 Availability Zone
    const vpc = new ec2.Vpc(this, 'DomjudgeVpc', {
      maxAzs: 1, 
      natGateways: 0,
      subnetConfiguration: [
        {
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
      ],
    });

    // 2. Persistent EBS Volume (Standalone)
    const volume = new ec2.Volume(this, 'DomjudgeDataVolume', {
      availabilityZone: vpc.availabilityZones[0],
      size: cdk.Size.gibibels(20),
      volumeType: ec2.EbsDeviceVolumeType.GP3,
      removalPolicy: cdk.RemovalPolicy.RETAIN, // Keep data even if stack is deleted
    });

    // 3. Static IP (Elastic IP)
    const eip = new ec2.CfnEIP(this, 'DomjudgeEIP');

    // 4. Security Group
    const securityGroup = new ec2.SecurityGroup(this, 'DomjudgeSG', {
      vpc,
      allowAllOutbound: true,
    });
    securityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80), 'Allow HTTP');
    securityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(22), 'Allow SSH');

    // 5. Auto Scaling Group
    const asg = new autoscaling.AutoScalingGroup(this, 'DomjudgeASG', {
      vpc,
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
      machineImage: ec2.MachineImage.latestAmazonLinux2023(),
      minCapacity: 1,
      maxCapacity: 1,
      securityGroup,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
    });

    // 6. Permissions for the instance to manage its own IP and Volume
    asg.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'ec2:AttachVolume',
        'ec2:DescribeVolumes',
        'ec2:AssociateAddress',
      ],
      resources: ['*'],
    }));

    // 7. UserData: Self-configuration on boot
    const volumeId = volume.volumeId;
    const staticIp = eip.ref;

    asg.addUserData(
      'yum update -y',
      'yum install -y docker git',
      'systemctl start docker',
      'systemctl enable docker',
      // Get Instance ID
      'TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")',
      'INSTANCE_ID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/instance-id)',
      // Associate Static IP
      `aws ec2 associate-address --instance-id $INSTANCE_ID --public-ip ${staticIp} --region ${this.region}`,
      // Attach EBS Volume
      `aws ec2 attach-volume --volume-id ${volumeId} --instance-id $INSTANCE_ID --device /dev/sdf --region ${this.region}`,
      // Wait for volume to be attached
      'sleep 10',
      // Format if new, then mount
      'mkdir -p /mnt/domjudge',
      'blkid /dev/sdf || mkfs -t xfs /dev/sdf',
      'mount /dev/sdf /mnt/domjudge',
      'echo "/dev/sdf /mnt/domjudge xfs defaults,nofail 0 2" >> /etc/fstab',
      // Install Docker Compose
      'curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose',
      'chmod +x /usr/local/bin/docker-compose'
    );

    // 8. CloudFront for HTTPS (Points to the Static IP)
    const cf = new cloudfront.Distribution(this, 'DomjudgeProxy', {
      defaultBehavior: {
        origin: new origins.HttpOrigin(eip.attrPublicIp),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER,
      },
    });

    new cdk.CfnOutput(this, 'StaticIP', { value: eip.ref });
    new cdk.CfnOutput(this, 'HttpsUrl', { value: `https://${cf.distributionDomainName}` });
  }
}
