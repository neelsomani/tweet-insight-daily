import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { NextRequest, NextResponse } from "next/server";

// Load environment variables
const AWS_REGION = process.env.AWS_REGION || "us-east-1";
const AWS_ACCESS_KEY_ID = process.env.AWS_ACCESS_KEY_ID;
const AWS_SECRET_ACCESS_KEY = process.env.AWS_SECRET_ACCESS_KEY;
const BUCKET_NAME = process.env.BUCKET_NAME;

const s3 = new S3Client({
  region: AWS_REGION,
  credentials: {
    accessKeyId: AWS_ACCESS_KEY_ID!,
    secretAccessKey: AWS_SECRET_ACCESS_KEY!,
  },
});

const streamToString = async (stream: any) =>
  await new Promise<string>((resolve, reject) => {
    const chunks: any[] = [];
    stream.on("data", (chunk: any) => chunks.push(chunk));
    stream.on("error", reject);
    stream.on("end", () => resolve(Buffer.concat(chunks).toString("utf-8")));
  });

export async function GET(request: NextRequest) {
  try {
    // Get date from query parameters, default to today
    const { searchParams } = new URL(request.url);
    const dateParam = searchParams.get('date');
    
    // Use provided date or default to today's date in YYYY-MM-DD format
    const date = dateParam || new Date().toISOString().split('T')[0];
    
    // Validate date format
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      return NextResponse.json({ error: "Invalid date format. Use YYYY-MM-DD" }, { status: 400 });
    }

    // Check if required environment variables are set
    if (!AWS_ACCESS_KEY_ID || !AWS_SECRET_ACCESS_KEY || !BUCKET_NAME) {
      return NextResponse.json({ 
        error: "Missing AWS credentials or bucket name. Check your environment variables." 
      }, { status: 500 });
    }

    const command = new GetObjectCommand({
      Bucket: BUCKET_NAME,
      Key: `${date}/summary.json`,
    });

    const response = await s3.send(command);
    const jsonStr = await streamToString(response.Body);
    const data = JSON.parse(jsonStr);

    return NextResponse.json(data);
  } catch (err) {
    console.error("S3 error:", err);
    return NextResponse.json({ error: "Failed to read S3 JSON" }, { status: 500 });
  }
} 