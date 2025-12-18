# Walkthrough - Deployment & CI/CD
I have implemented a GitHub Actions workflow to automate code deployment.

## GitHub Actions Setup
Add Secrets: Go to your GitHub Repository -> Settings -> Secrets and variables -> Actions.

### Create Repository Secrets:

```
AWS_ACCESS_KEY_ID: Your AWS Access Key.
AWS_SECRET_ACCESS_KEY: Your AWS Secret Key.
AWS_REGION: ca-central-1 (or your active region).
```

Branching & Deployment Strategy
dev Branch: This is your working branch. Push all your changes here first.
```
git checkout dev
git add .
git commit -m "feat: my new feature"
git push origin dev
```

```main``` Branch: This is your production branch. Merging to main triggers the deployment.

```
git checkout main
git merge dev
git push origin main
```

Watch the "Actions" tab in GitHub for the deployment status

## Manual Infrastructure Changes
**IMPORTANT**

The GitHub Action ONLY updates the Lambda code (aws_lambda_function.py).

If you modify main.tf (changing environment variables or infrastructure), you must still run Terraform locally:

```
terraform apply -var="..."
```