Content-Type: multipart/mixed; boundary="//"
MIME-Version: 1.0

--//
Content-Type: text/cloud-config; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: attachment; filename="cloud-config.txt"

#cloud-config
cloud_final_modules:
- [scripts-user, always]

--//
Content-Type: text/x-shellscript; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: attachment; filename="001.txt"

#!/bin/bash
# IMP: cloud-init will have old user scriptf files as well; it executes them in sorted order
# by naming file 001.txt we want it to execute first and code in 001.txt file will delete all user script files except 001.txt 

S3_BUCKET="${s3_bucket}"
S3_LOCATION="${s3_location}"
S3_AC_KEY="${s3_access_key}"
S3_SC_KEY="${s3_secret_key}"
WH_PW="${webhook_pw}"
REGION="${region}"
VERSION="${thorny_version}"   # git tag of the release, e.g. thorny-v0.1.0

curl -fsSL "https://raw.githubusercontent.com/eliasheithecker/cthorny/$VERSION/thorny/deploy/startup.sh" \
  | THORNY_VERSION="$VERSION" bash -s -- "$S3_BUCKET" "$S3_LOCATION" "$S3_AC_KEY" "$S3_SC_KEY" "$WH_PW" "aws" "$REGION"


--//--
