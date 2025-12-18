import json
import urllib.parse
import urllib.request
import os
import boto3
import time
import base64
from datetime import datetime

# Configuration
# Set these in AWS Lambda Environment Variables
RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY')
LOG_BUCKET_NAME = os.environ.get('LOG_BUCKET_NAME')

# Jira Configuration
JIRA_DOMAIN = os.environ.get('JIRA_DOMAIN')
JIRA_EMAIL = os.environ.get('JIRA_EMAIL')
JIRA_API_TOKEN = os.environ.get('JIRA_API_TOKEN')
JIRA_PROJECT_KEY = os.environ.get('JIRA_PROJECT_KEY')

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

def create_jira_issue(data, form_type):
    if not all([JIRA_DOMAIN, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY]):
        print("Jira configuration missing, skipping issue creation")
        return None

    url = f"https://{JIRA_DOMAIN}/rest/api/3/issue"
    
    # Basic Auth
    auth_str = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
    auth_bytes = auth_str.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    summary = f"[{form_type}] Submission from {data.get('firstName', 'Unknown')} {data.get('lastName', '')}"
    
    payload = {
                "fields": {
                    "project": {
                        "key": "PC"
                    },
                    "summary": summary,
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "" if form_type == "download_resume" else data.get('notes')
                                    }
                                ]
                            }
                        ]
                    },
                    "issuetype": {
                        "name": "Lead"
                    },
                    "customfield_10202": data.get('firstName'),
                    "customfield_10204":data.get('lastName'),
                    "customfield_10203": data.get('email'),
                    "customfield_10207": "" if form_type == "download_resume" else data.get('phone') ,
                    "customfield_10205":  { "id": "10256" if form_type == "download_resume" else data.get('whoAreYou')  },
                    "customfield_10208":  [ form_type ]
            }
        }
    

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"Jira API Error: {e.code} - {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        print(f"Jira Integration Error: {str(e)}")
        return None

def lambda_handler(event, context):
    try:
        if isinstance(event.get('body'), str):
            body = json.loads(event.get('body', '{}'))
        else:
            body = event.get('body', {})
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

        # 3. Create Jira Issue
        jira_result = create_jira_issue(form_data, form_type)
        if jira_result:
            print(f"Jira issue created: {jira_result.get('key')}")
            log_entry['jira_issue'] = jira_result.get('key')
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'message': 'Success', 'id': file_name, 'jira_issue': jira_result.get('key') if jira_result else None})
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': 'Internal Server Error'})
        }
