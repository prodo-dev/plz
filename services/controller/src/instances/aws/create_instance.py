import boto3

client = boto3.client('ec2')


# TODO(samir): make this into a proper variable
ami_tag = "2018-03-01"

response = client.describe_images(
    Filters=[
        {
            'Name': 'name',
            'Values': [
                'plz-worker-' + ami_tag,
                ]
        },
    ],
)
ami_id = response['Images'][0]['ImageId']

_BASE_INSTANCE_SPEC = {
    # TODO(sergio): check with Samir. Should we care about the subnet id?
    # It's getting the same as the workers. Will it always be the case?

    'InstanceType': 't1.micro',
    'ImageId': ami_id,
    'TagSpecifications': [
        {
            'ResourceType': 'instance',
            'Tags': [
                {
                   'Key': 'Name',
                   'Value': 'buuuuuu'
                },
            ]
        },
    ],
    'InstanceMarketOptions': {
        'MarketType': 'spot',
        'SpotOptions': {
            'MaxPrice': '1.0',
        }
    },
    'BlockDeviceMappings': [
        {
            'DeviceName': '/dev/sdx',
            'Ebs': {
                'VolumeSize': 100,
            },
        },
    ]
}

response = client.run_instances(**_BASE_INSTANCE_SPEC, MinCount=1, MaxCount=1)

#
# response = client.run_instances(
#     InstanceType='t1.micro',
#     ImageId=ami_id,
#     TagSpecifications=[
#         {
#             'ResourceType': 'instance',
#             'Tags': [
#                 {
#                     'Key': 'Name',
#                     'Value': 'buuuuuu'
#                 },
#             ]
#         },
#     ],
#     InstanceMarketOptions={
#         'MarketType': 'spot',
#         'SpotOptions': {
#             'MaxPrice': '1.0',
#         }
#     },
#     BlockDeviceMappings=[
#         {
#             'DeviceName': '/dev/sdx',
#             'Ebs': {
#                 'VolumeSize': 100,
#             },
#         },
#     ],
#     MinCount=1,
#     MaxCount=1)
print(response['Instances'][0]['PrivateDnsName'])

