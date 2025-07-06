"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { TrendingUp, AlertCircle, ChevronLeft, ChevronRight } from "lucide-react";

interface NewsData {
  timestamp: number;
  latest_news: {
    [key: string]: string;
  };
}

export default function S3DataDisplay() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [data, setData] = useState<NewsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasInitialized, setHasInitialized] = useState(false);
  
  // Get date from URL or default to current UTC date
  const getInitialDate = () => {
    const urlDate = searchParams.get('utc_date');
    if (urlDate && /^\d{4}-\d{2}-\d{2}$/.test(urlDate)) {
      return urlDate;
    }
    return new Date().toISOString().split('T')[0];
  };
  
  const [selectedDate, setSelectedDate] = useState<string>(getInitialDate);

  const getLocalDateForDisplay = (utcDate: string) => {
    // Convert UTC date to local date for display
    const date = new Date(utcDate + 'T00:00:00Z');
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const fetchData = async (date: string, checkPreviousDays: boolean = false) => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`/api/s3-data?date=${date}`);
      
      if (!response.ok) {
        const errorData = await response.json();
        // If it's the "Failed to read S3 JSON" error, treat it as no data
        if (errorData.error === "Failed to read S3 JSON") {
          // If we're checking previous days and this is the initial load, try previous day
          if (checkPreviousDays && !searchParams.get('utc_date') && !hasInitialized) {
            const currentDate = new Date(date + 'T00:00:00Z');
            currentDate.setDate(currentDate.getDate() - 1);
            const previousDate = currentDate.toISOString().split('T')[0];
            
            // Try previous day
            const prevResponse = await fetch(`/api/s3-data?date=${previousDate}`);
            if (prevResponse.ok) {
              const prevData = await prevResponse.json();
              setData(prevData);
              setSelectedDate(previousDate);
              // Update URL to reflect the actual date we found data for
              const params = new URLSearchParams(searchParams);
              params.set('utc_date', previousDate);
              router.push(`?${params.toString()}`);
              setHasInitialized(true);
              return;
            }
          }
          setData(null);
          return;
        }
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }
      
      const jsonData = await response.json();
      setData(jsonData);
    } catch (err) {
      console.error("Error fetching S3 data:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  // Initial load effect - only runs once
  useEffect(() => {
    const urlDate = searchParams.get('utc_date');
    if (!urlDate && !hasInitialized) {
      // Initial load without URL param - check previous days
      fetchData(selectedDate, true);
    } else {
      // URL param exists or already initialized - just fetch normally
      fetchData(selectedDate, false);
    }
    setHasInitialized(true);
  }, []); // Empty dependency array - only runs once

  // Navigation effect - runs when selectedDate changes
  useEffect(() => {
    if (hasInitialized) {
      fetchData(selectedDate, false);
    }
  }, [selectedDate, hasInitialized]);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp * 1000); // Convert Unix timestamp to milliseconds
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  const changeDate = (direction: 'prev' | 'next') => {
    const currentDate = new Date(selectedDate + 'T00:00:00Z');
    if (direction === 'prev') {
      currentDate.setDate(currentDate.getDate() - 1);
    } else {
      currentDate.setDate(currentDate.getDate() + 1);
    }
    const newDate = currentDate.toISOString().split('T')[0];
    setSelectedDate(newDate);
    
    // Update URL
    const params = new URLSearchParams(searchParams);
    params.set('utc_date', newDate);
    router.push(`?${params.toString()}`);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        {/* Date navigation skeleton */}
        <div className="flex items-center justify-center gap-4 mb-8">
          <Skeleton className="h-10 w-10 rounded-full" />
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-10 w-10 rounded-full" />
        </div>

        {/* News cards skeleton */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="border-0 shadow-sm bg-white/60 backdrop-blur-sm">
              <CardHeader className="pb-3">
                <Skeleton className="h-6 w-3/4 mb-2" />
                <Skeleton className="h-4 w-1/2" />
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-5/6" />
                  <Skeleton className="h-4 w-4/5" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-red-200 bg-red-50/50 backdrop-blur-sm">
        <CardContent className="p-8">
          <div className="flex items-center gap-3 text-red-600 mb-4">
            <AlertCircle className="w-6 h-6" />
            <h3 className="text-lg font-semibold">Error Loading Data</h3>
          </div>
          <p className="text-red-600 mb-4">{error}</p>
          <Button 
            onClick={() => fetchData(selectedDate)}
            variant="outline"
            className="border-red-300 text-red-600 hover:bg-red-50"
          >
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!data || !data.latest_news) {
    return (
      <div className="space-y-8">
        {/* Simple Date Navigation */}
        <div className="flex items-center justify-center gap-4">
          <Button
            variant="outline"
            size="icon"
            onClick={() => changeDate('prev')}
            className="rounded-full w-10 h-10 border-slate-200 hover:bg-slate-50"
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="text-lg font-medium text-slate-700">
            {formatDate(getLocalDateForDisplay(selectedDate))}
          </span>
          <Button
            variant="outline"
            size="icon"
            onClick={() => changeDate('next')}
            className="rounded-full w-10 h-10 border-slate-200 hover:bg-slate-50"
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>

        <Card className="border-0 shadow-sm bg-white/60 backdrop-blur-sm">
          <CardContent className="p-8 text-center">
            <h3 className="text-lg font-semibold text-slate-800 mb-2">No Data Available</h3>
            <p className="text-slate-600 mb-4">
              No news data was found for the selected date.
            </p>
            <Button 
              onClick={() => fetchData(selectedDate)}
              variant="outline"
            >
              Refresh
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const newsEntries = Object.entries(data.latest_news);

  return (
    <div className="space-y-8">
      {/* Simple Date Navigation */}
      <div className="flex items-center justify-center gap-4">
        <Button
          variant="outline"
          size="icon"
          onClick={() => changeDate('prev')}
          className="rounded-full w-10 h-10 border-slate-200 hover:bg-slate-50"
        >
          <ChevronLeft className="w-4 h-4" />
        </Button>
        <div className="text-center">
          <div className="text-lg font-medium text-slate-700">
            {getLocalDateForDisplay(selectedDate)}
          </div>
          <div className="text-sm text-slate-500">
            Updated {formatTimestamp(data.timestamp)}
          </div>
        </div>
        <Button
          variant="outline"
          size="icon"
          onClick={() => changeDate('next')}
          className="rounded-full w-10 h-10 border-slate-200 hover:bg-slate-50"
        >
          <ChevronRight className="w-4 h-4" />
        </Button>
      </div>

      {/* News Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {newsEntries.map(([title, content], index) => (
          <Card 
            key={title} 
            className="border-0 shadow-sm bg-white/60 backdrop-blur-sm hover:shadow-md transition-all duration-200 hover:scale-[1.02] group"
          >
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <span className="text-xs text-slate-400 font-mono">
                  #{String(index + 1).padStart(2, '0')}
                </span>
              </div>
              <CardTitle className="text-lg font-bold text-slate-800 group-hover:text-blue-600 transition-colors">
                {title}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-slate-600 leading-relaxed">
                {content}
              </CardDescription>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
} 