#!/usr/bin/env zsh

set -e
set -u
set -o pipefail

HERE=${0:a:h}
ROOT=${HERE:h:h}
SCRIPT=$0

function usage {
  echo "Usage: ${SCRIPT} NAME@prodo.ai OUTPUT-FILE.zip"
  exit 2
}

[[ $# -eq 2 ]] || usage

EMAIL=$1
[[ $EMAIL =~ 'prodo\.ai$' ]] || usage
NAME=${EMAIL%@prodo.ai}
COMMON_NAME=client-$NAME

OUTPUT_FILE=$2
[[ $OUTPUT_FILE =~ '\.zip$' ]] || usage

EASY_RSA='/usr/share/easy-rsa'
KEY_DIR='/keys'
ENVIRONMENT=(
  "OPENSSL=openssl"
  "PKCS11TOOL=pkcs11-tool"
  "GREP=grep"
  "KEY_CONFIG='${EASY_RSA}/openssl-1.0.0.cnf'"
  "KEY_DIR=${KEY_DIR}"
  "KEY_SIZE=2048"
  "CA_EXPIRE=3650"
  "KEY_EXPIRE=3650"
  "KEY_NAME='OpenVPN'"
  "KEY_ORG='Prodo Tech Ltd.'"
  "KEY_OU='Infrastructure'"
  "KEY_EMAIL='webmaster@prodo.ai'"
  "KEY_CITY='London'"
  "KEY_PROVINCE='England'"
  "KEY_COUNTRY='GB'"
)

SSH_CONNECTION=ubuntu@knockknock.prodo.ai
SSH_PRIVATE_KEY_FILE="${ROOT}/machines/keys/batman.privkey"
SSH=(ssh -i $SSH_PRIVATE_KEY_FILE $SSH_CONNECTION --)
SCP=(scp -i $SSH_PRIVATE_KEY_FILE --)

$SSH "[[ -f '${KEY_DIR}/${COMMON_NAME}.key' ]]" || {
  echo 'Generating key...'
  $SSH "${ENVIRONMENT[@]}" "${EASY_RSA}/pkitool" $COMMON_NAME
}
echo 'Copying client files...'
OUTPUT_DIR=$(mktemp)
rm $OUTPUT_DIR
mkdir $OUTPUT_DIR
cp -v "${HERE}/client.conf" $OUTPUT_DIR/prodo-ai.ovpn
$SCP ubuntu@knockknock.prodo.ai:${KEY_DIR}/ca.crt $OUTPUT_DIR/ca.crt
$SCP ubuntu@knockknock.prodo.ai:${KEY_DIR}/${COMMON_NAME}.crt $OUTPUT_DIR/client.crt
$SCP ubuntu@knockknock.prodo.ai:${KEY_DIR}/${COMMON_NAME}.csr $OUTPUT_DIR/client.csr
$SCP ubuntu@knockknock.prodo.ai:${KEY_DIR}/${COMMON_NAME}.key $OUTPUT_DIR/client.key
(cd $OUTPUT_DIR && zip $OUTPUT_FILE *)
rm -rf $OUTPUT_DIR
echo 'Done.'
