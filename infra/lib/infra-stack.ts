import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as fs from 'fs';
import * as path from 'path';

export class InfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const sshPublicKey = this.node.tryGetContext('sshPublicKey') as string;
    if (!sshPublicKey) {
      throw new Error('sshPublicKey context is required. Add it to cdk.json under "context".');
    }

    // 1. Default VPC
    const vpc = ec2.Vpc.fromLookup(this, 'DefaultVpc', { isDefault: true });

    // 2. Persistent EBS Volume — RETAIN keeps data even if stack is deleted
    const volume = new ec2.Volume(this, 'DomjudgeDataVolume', {
      availabilityZone: vpc.availabilityZones[0],
      size: cdk.Size.gibibytes(20),
      volumeType: ec2.EbsDeviceVolumeType.GP3,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // 3. Static IP (Elastic IP)
    const eip = new ec2.CfnEIP(this, 'DomjudgeEIP');

    // 4. SSH Key Pair
    const keyPair = new ec2.KeyPair(this, 'DomjudgeKeyPair', {
      publicKeyMaterial: sshPublicKey,
    });

    // 5. Security Group
    const securityGroup = new ec2.SecurityGroup(this, 'DomjudgeSG', {
      vpc,
      allowAllOutbound: true,
    });
    securityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80), 'HTTP');
    securityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(22), 'SSH key-only');

    // 6. UserData: inject CDK-resolved values then run the shared script
    const userData = ec2.UserData.forLinux();
    const userDataLines = fs.readFileSync(path.join(__dirname, 'user-data.sh'), 'utf-8').split('\n');
    userData.addCommands(
      `export VOLUME_ID="${volume.volumeId}"`,
      `export AWS_REGION="${this.region}"`,
      ...userDataLines,
    );

    // 7. EC2 Instance
    const instance = new ec2.Instance(this, 'DomjudgeInstance', {
      vpc,
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
      machineImage: ec2.MachineImage.fromSsmParameter(
        '/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id',
        { os: ec2.OperatingSystemType.LINUX },
      ),
      securityGroup,
      keyPair,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      userData,
      blockDevices: [{
        deviceName: '/dev/sda1',
        volume: ec2.BlockDeviceVolume.ebs(30, {
          volumeType: ec2.EbsDeviceVolumeType.GP3,
        }),
      }],
    });

    // 8. Associate EIP — done by CloudFormation, no AWS CLI needed in UserData
    new ec2.CfnEIPAssociation(this, 'EIPAssociation', {
      instanceId: instance.instanceId,
      allocationId: eip.attrAllocationId,
    });

    // 9. Attach EBS volume — done by CloudFormation, UserData waits for device to appear
    new ec2.CfnVolumeAttachment(this, 'VolumeAttachment', {
      instanceId: instance.instanceId,
      volumeId: volume.volumeId,
      device: '/dev/sdf',
    });

    new cdk.CfnOutput(this, 'StaticIP', { value: eip.attrPublicIp });
    new cdk.CfnOutput(this, 'AppUrl', { value: `http://${eip.attrPublicIp}` });
  }
}
