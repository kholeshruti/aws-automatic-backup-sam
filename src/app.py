import boto3
import os
import uuid
from datetime import datetime, timezone

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

SOURCE_BUCKET = os.environ['SOURCE_BUCKET']
BACKUP_BUCKET = os.environ['BACKUP_BUCKET']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
TABLE_NAME = os.environ['TABLE_NAME']

table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    backup_id = str(uuid.uuid4())
    run_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S')
    files_copied = 0
    status = 'SUCCESS'
    error_message = ''

    try:
        response = s3.list_objects_v2(Bucket=SOURCE_BUCKET)
        objects = response.get('Contents', [])

        if not objects:
            status = 'NO_FILES'
        else:
            for obj in objects:
                key = obj['Key']
                destination_key = f"backups/{run_timestamp}/{key}"

                s3.copy_object(
                    CopySource={'Bucket': SOURCE_BUCKET, 'Key': key},
                    Bucket=BACKUP_BUCKET,
                    Key=destination_key
                )
                files_copied += 1

    except Exception as e:
        status = 'FAILED'
        error_message = str(e)

    table.put_item(Item={
        'backupId': backup_id,
        'timestamp': run_timestamp,
        'filesCopied': files_copied,
        'status': status,
        'errorMessage': error_message
    })

    if status == 'SUCCESS':
        message = f"Backup completed successfully.\nFiles copied: {files_copied}\nTimestamp: {run_timestamp}"
    elif status == 'NO_FILES':
        message = f"Backup ran but found no files in {SOURCE_BUCKET}.\nTimestamp: {run_timestamp}"
    else:
        message = f"Backup FAILED.\nError: {error_message}\nTimestamp: {run_timestamp}"

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"Backup {status} - {run_timestamp}",
        Message=message
    )

    return {
        'statusCode': 200,
        'body': {
            'backupId': backup_id,
            'status': status,
            'filesCopied': files_copied
        }
    }