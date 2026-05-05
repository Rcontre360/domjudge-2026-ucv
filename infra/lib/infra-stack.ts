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

    const sshPublicKey = this.node.tryGetContext('sshPublicKey') as string;
    if (!sshPublicKey) {
      throw new Error('sshPublicKey context is required. Add it to cdk.json under "context".');
    }

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
      machineImage: ec2.MachineImage.latestAmazonLinux2023(),
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

    // 8. UserData: runs on every boot — self-heals EIP + EBS, then starts the app
    const volumeId = volume.volumeId;
    const allocationId = eip.ref; // eip.ref resolves to allocation ID for VPC EIPs

    asg.addUserData(
      'yum update -y',
      'yum install -y docker git nvme-cli',
      'systemctl start docker',
      'systemctl enable docker',

      // Fetch instance ID via IMDSv2
      'TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")',
      'INSTANCE_ID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/instance-id)',

      // Associate the static Elastic IP — eip.ref is the allocation ID, so use --allocation-id
      `aws ec2 associate-address --instance-id $INSTANCE_ID --allocation-id ${allocationId} --region ${this.region}`,

      // Attach the persistent EBS volume
      `aws ec2 attach-volume --volume-id ${volumeId} --instance-id $INSTANCE_ID --device /dev/sdf --region ${this.region}`,

      // Wait until AWS reports the volume as in-use before trying to mount
      `aws ec2 wait volume-in-use --volume-ids ${volumeId} --region ${this.region}`,
      'sleep 5',

      // On Nitro-based instances (t3), /dev/sdf is exposed as an NVMe device.
      // Resolve the real device via the stable by-id symlink using the volume ID.
      `DEVICE=$(readlink -f /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_$(echo "${volumeId}" | sed 's/-//'))`,

      'mkdir -p /mnt/domjudge',
      'blkid $DEVICE || mkfs -t xfs $DEVICE',
      'mount $DEVICE /mnt/domjudge',
      `echo "$DEVICE /mnt/domjudge xfs defaults,nofail 0 2" >> /etc/fstab`,

      // Install Docker Compose
      'curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose',
      'chmod +x /usr/local/bin/docker-compose',

      // Clone repo on first boot; pull updates on subsequent boots
      'cd /mnt/domjudge',
      'if [ ! -d ".git" ]; then git clone https://github.com/Rcontre360/domjudge-2026-ucv.git .; else git pull; fi',

      // Start the app
      'docker-compose up -d',
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
