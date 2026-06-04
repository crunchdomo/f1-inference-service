"use client";

import { useState, useEffect, FormEvent } from "react";
import useSWR from "swr";
import { PredictionForm } from "@/components/prediction-form";
import { ResultDisplay } from "@/components/result-display";
import { F1Logo } from "@/components/f1-logo";

interface Options {
  drivers: string[];
  constructors: string[];
  circuits: string[];
  seasons: number[];
}

interface PredictionResult {
  podium_probability: number;
  podium_likely: boolean;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function Home() {
  const { data: options, isLoading: optionsLoading, error: optionsError } = useSWR<Options>(
    "http://localhost:8000/options",
    fetcher
  );

  const [result, setResult] = useState<PredictionResult | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleSubmit = async (formData: {
    grid: number;
    driver: string;
    constructor: string;
    circuit: string;
    season: number;
  }) => {
    setIsSubmitting(true);
    setSubmitError(null);
    setResult(null);

    try {
      const response = await fetch("http://localhost:8000/predict-sync", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error("Prediction request failed");
      }

      const data = await response.json();
      setResult(data);
    } catch (error) {
      setSubmitError("Failed to get prediction. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen px-4 py-8 md:py-16">
      <div className="mx-auto max-w-2xl">
        <header className="mb-12 text-center">
          <div className="mb-6 flex justify-center">
            <F1Logo />
          </div>
          <h1 className="mb-2 text-3xl font-bold tracking-tight text-[var(--foreground)] md:text-4xl">
            Podium Predictor
          </h1>
          <p className="text-[var(--muted-foreground)]">
            Enter race details to predict podium probability
          </p>
        </header>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 md:p-8">
          {optionsError && (
            <div className="mb-6 rounded-lg bg-red-900/20 border border-red-800 p-4 text-red-400">
              Failed to load options. Make sure the API server is running.
            </div>
          )}

          <PredictionForm
            options={options}
            isLoading={optionsLoading}
            isSubmitting={isSubmitting}
            onSubmit={handleSubmit}
          />

          {submitError && (
            <div className="mt-6 rounded-lg bg-red-900/20 border border-red-800 p-4 text-red-400">
              {submitError}
            </div>
          )}

          {(isSubmitting || result) && (
            <div className="mt-8 border-t border-[var(--border)] pt-8">
              <ResultDisplay result={result} isLoading={isSubmitting} />
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
