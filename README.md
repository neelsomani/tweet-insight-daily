# Today on Tech Twitter

A Next.js application that displays daily tech Twitter insights and analytics.

## Features

- Fetches JSON data from AWS S3 bucket
- Displays data in a clean, modern UI
- Loading states and error handling
- Responsive design

## Setup

1. Install dependencies:
```bash
npm install
# or
pnpm install
```

2. Create a `.env.local` file in the root directory with the following variables:
```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
BUCKET_NAME=your_s3_bucket_name_here
```

3. The S3 key format is automatically set to `{date}/summary.json` where `{date}` is in YYYY-MM-DD format.
   Make sure your S3 bucket has files organized like:
   ```
   your-bucket/
   ├── 2025-01-15/
   │   └── summary.json
   ├── 2025-01-16/
   │   └── summary.json
   └── ...
   ```

4. Run the development server:
```bash
npm run dev
# or
pnpm dev
```

## AWS S3 Configuration

Make sure your AWS credentials have the following permissions:
- `s3:GetObject` for the specific bucket and key
- The bucket should contain JSON files that can be parsed

## API Endpoints

- `GET /api/s3-data?date=YYYY-MM-DD` - Fetches JSON data from S3 for a specific date
  - `date` parameter is optional, defaults to today's date
  - Date format must be YYYY-MM-DD (e.g., 2025-01-15)

## Components

- `S3DataDisplay` - Main component that fetches and displays S3 data
- Uses shadcn/ui components for consistent styling

## Environment Variables

- `AWS_REGION` - AWS region (defaults to us-east-1)
- `AWS_ACCESS_KEY_ID` - AWS access key ID
- `AWS_SECRET_ACCESS_KEY` - AWS secret access key
- `BUCKET_NAME` - S3 bucket name containing the JSON files 