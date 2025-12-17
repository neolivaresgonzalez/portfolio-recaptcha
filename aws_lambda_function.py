import json
import urllib.parse
import urllib.request
import os
import boto3
import time
from datetime import datetime

# Configuration
# Set these in AWS Lambda Environment Variables
RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY')
LOG_BUCKET_NAME = os.environ.get('LOG_BUCKET_NAME')

s3 = boto3.client('s3')

def verify_recaptcha(token):
    url = 'https://www.google.com/recaptcha/api/siteverify'
    data = urllib.parse.urlencode({
        'secret': RECAPTCHA_SECRET_KEY,
        'response': token
    }).encode('utf-8')

    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        return result

def lambda_handler(event, context):
    try:
        # Handle CORS for OPTIONS request (if not handled by Function URL config)
        if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
             return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': ''
            }

        body = json.loads(event.get('body', '{}'))
        token = body.get('token')
        form_data = body.get('formData', {})
        form_type = body.get('formType', 'contact') # 'contact' or 'download_resume'

        if not token:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing reCAPTCHA token'})
            }

        # 1. Verify reCAPTCHA
        verification = verify_recaptcha(token)
        
        if not verification.get('success') or verification.get('score', 0) < 0.5:
             print(f"Recaptcha Failed: {verification}")
             return {
                'statusCode': 400,
                'body': json.dumps({'error': 'reCAPTCHA verification failed', 'details': verification})
            }

        # 2. Log to S3
        timestamp = datetime.now().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'form_type': form_type,
            'data': form_data,
            'verification_score': verification.get('score')
        }
        
        file_name = f"logs/{form_type}/{int(time.time())}_{form_data.get('email', 'anon')}.json"
        
        if LOG_BUCKET_NAME:
            s3.put_object(
                Bucket=LOG_BUCKET_NAME,
                Key=file_name,
                Body=json.dumps(log_entry),
                ContentType='application/json'
            )
        else:
            print("LOG_BUCKET_NAME not set, skipping S3 upload")

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*', 
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'message': 'Success', 'id': file_name})
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Internal Server Error'})
        }
