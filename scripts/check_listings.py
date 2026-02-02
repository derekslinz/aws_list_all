from aws_list_all.introspection import get_services, get_listing_operations

expected_no_listings = {
    'account','amplifyuibuilder','appconfigdata','application-autoscaling','bedrock-runtime','braket','budgets',
    'chime-sdk-meetings','chime-sdk-messaging','cloudtrail-data','connect-contact-lens','connectparticipant',
    'controltower','ebs','ec2-instance-connect','forecastquery','glacier','health','honeycode','identitystore',
    'iot-jobs-data','iotevents-data','kinesis-video-signaling','kinesis-video-webrtc-storage','lex-runtime',
    'lexv2-runtime','managedblockchain-query','marketplace-catalog','marketplace-entitlement','marketplacecommerceanalytics',
    'mediaconvert','meteringmarketplace','payment-cryptography-data','personalize-events','personalize-runtime','pi',
    'pinpoint-sms-voice','pricing','qldb-session','quicksight','rbin','rds-data','resourcegroupstaggingapi','sagemaker-a2i-runtime',
    'sagemaker-edge','sagemaker-featurestore-runtime','sagemaker-metrics','sagemaker-runtime','sso','sso-oidc','sts','swf','wafv2','workdocs','workmailmessageflow'
}

services_with_no_listings = set()
for service in get_services():
    if len(get_listing_operations(service, region='us-east-1')) == 0:
        services_with_no_listings.add(service)

print('expected_no_listings - services_with_no_listings =')
print(sorted(list(expected_no_listings - services_with_no_listings)))
print('services_with_no_listings - expected_no_listings =')
print(sorted(list(services_with_no_listings - expected_no_listings)))
