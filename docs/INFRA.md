# Infrastructure

The `infra/` directory holds an [AWS CDK](https://aws.amazon.com/cdk/)
(TypeScript) application that provisions the AWS resources required to run the
DomJudge stack. The whole stack lives in `infra/lib/infra-stack.ts` and the
machine bootstrap script in `infra/lib/user-data.sh`.

## What gets created

A single CDK stack (`InfraStack`) creates the following resources in the
account's default VPC:

| Resource                      | Purpose                                                       |
|-------------------------------|---------------------------------------------------------------|
| **EC2 instance** (`t3.medium`, Ubuntu 24.04) | Host running Docker and the DomJudge containers. |
| **Elastic IP**                | Stable public address attached to the instance.               |
| **EBS volume** (20 GiB, gp3)  | Persistent data volume, mounted at `/mnt/domjudge`. Marked `RETAIN` so contest data survives stack deletion. |
| **SSH key pair**              | Public key from `cdk.json` context is uploaded so you can SSH in with the matching private key. |
| **Security group**            | Allows inbound TCP on `:22` (SSH) and `:80` (HTTP) from anywhere; egress is open. |
| **EIP association**           | Attaches the Elastic IP to the instance.                      |
| **Volume attachment**         | Attaches the persistent EBS volume to the instance as `/dev/sdf`. |

CDK outputs the public IP (`StaticIP`) and a convenience URL (`AppUrl`) when
the stack finishes deploying.

## Where the DomJudge stack lives on the instance

After provisioning, **the docker-compose stack is deployed at
`/mnt/domjudge/`** on the EC2 instance. That directory is the mount point of
the persistent EBS volume, so the cloned repository and all Docker named
volumes survive instance replacement.

To reach it:

```bash
./connect.sh                  # SSH into the instance
cd /mnt/domjudge              # repository root on the host
docker-compose ps             # inspect the running stack
docker-compose logs -f        # tail logs
docker-compose pull && docker-compose up -d   # update DomJudge images
```

The Docker daemon stores its named volumes (`mariadb-data`,
`domserver-data`) under `/var/lib/docker/volumes/` on the same disk.

## What the bootstrap does

The CDK injects two environment variables (`VOLUME_ID`, `AWS_REGION`) into the
`UserData` and then runs `user-data.sh`. At a high level, on first boot the
instance:

1. Installs Docker, Docker Compose, Git, and a few utilities (`apt-get`).
2. Waits for the attached EBS volume to show up as an NVMe device, formats it
   as XFS if it is empty, mounts it at `/mnt/domjudge`, and adds an `/etc/fstab`
   entry so the mount survives reboots.
3. Clones the public deployment repository
   (`Rcontre360/domjudge-2026-ucv`) into `/mnt/domjudge`. If the directory
   already contains a Git checkout (after a re-launch) it runs `git pull`
   instead.
4. Runs `docker-compose up -d` from that directory, which starts the
   domserver, MariaDB, two judgehosts, and the one-shot `setup` container that
   applies the admin and judgehost passwords from the `.env` file.

Because the EBS volume is retained and the user-data script is idempotent,
replacing the EC2 instance is safe: the new VM mounts the same volume and
finds the contest data already in place.

## Deploying the stack

The commands below assume you have an AWS account, Node.js 20+, and the
TypeScript toolchain installed. All commands run from `infra/`.

### One-time AWS account setup

1. **Install the AWS CLI.** Pick the package manager for your OS or follow
   <https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html>.
2. **Create an IAM user (or SSO profile) with admin-equivalent permissions**
   needed to create EC2, EBS, EIP, IAM key pairs, and CloudFormation stacks.
3. **Configure a local profile**:

   ```bash
   aws configure                # interactive: access key, secret, region
   # or, for SSO:
   aws configure sso
   ```

   This writes credentials to `~/.aws/credentials` and a default region to
   `~/.aws/config`. Verify with:

   ```bash
   aws sts get-caller-identity
   ```

4. **Install the CDK CLI** globally (or use the local `npx cdk` shipped via
   the dev dependency in `infra/package.json`):

   ```bash
   npm install -g aws-cdk
   ```

5. **Bootstrap the target account/region.** CDK needs an S3 bucket and IAM
   roles in every account/region it deploys to:

   ```bash
   cd infra
   npm install
   npx cdk bootstrap aws://<ACCOUNT_ID>/<REGION>
   ```

### Configuring the SSH public key

The stack expects an SSH public key in `infra/cdk.json` under
`context.sshPublicKey`. Replace the placeholder with the key you want to use
to SSH into the EC2 instance:

```json
"context": {
  "sshPublicKey": "ssh-ed25519 AAAA... user@host",
  ...
}
```

Keep the matching private key in `keys/ssh` (referenced by `connect.sh`) with
permissions `600`.

### Deploying

From `infra/`:

```bash
npm install                # first time only
npx cdk synth              # render the CloudFormation template
npx cdk diff               # show changes against the deployed stack
npx cdk deploy             # create or update the stack
```

The first deploy takes ~5 minutes and prints the static IP and the web URL
when finished. Subsequent deploys are usually incremental.

To tear everything down (the EBS volume is intentionally retained):

```bash
npx cdk destroy
```

After destroying, the orphaned EBS volume can be deleted manually from the EC2
console or with `aws ec2 delete-volume --volume-id vol-XXXX` if you want to
fully clean up.

## Troubleshooting

- **`cdk deploy` complains about missing context for the default VPC.** CDK
  caches account-specific lookups in `infra/cdk.context.json`. Make sure your
  AWS credentials point to the account that contains the VPC; delete the file
  if you switch accounts.
- **SSH says `Permission denied (publickey)`.** Verify `keys/ssh` is the
  private key matching the public key stored under `context.sshPublicKey` and
  that its permissions are `600`.
- **`docker-compose` is missing on the instance after first boot.** UserData
  is run only once. Check `/var/log/cloud-init-output.log` on the instance for
  errors and re-run `bash /mnt/domjudge/.../user-data.sh` manually if needed.
