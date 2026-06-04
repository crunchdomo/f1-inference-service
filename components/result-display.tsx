"use client";

interface PredictionResult {
  podium_probability: number;
  podium_likely: boolean;
}

interface ResultDisplayProps {
  result: PredictionResult | null;
  isLoading: boolean;
}

export function ResultDisplay({ result, isLoading }: ResultDisplayProps) {
  const probability = result?.podium_probability ?? 0;
  const percentage = Math.round(probability * 100);
  const circumference = 2 * Math.PI * 80;
  const strokeDashoffset = circumference - (probability * circumference);

  return (
    <div className="flex flex-col items-center">
      <h3 className="mb-6 text-lg font-semibold text-[var(--foreground)]">
        Prediction Result
      </h3>

      <div className="relative mb-6">
        <svg
          width="200"
          height="200"
          viewBox="0 0 200 200"
          className="transform -rotate-90"
        >
          {/* Background circle */}
          <circle
            cx="100"
            cy="100"
            r="80"
            fill="none"
            stroke="var(--muted)"
            strokeWidth="12"
          />
          {/* Progress circle */}
          <circle
            cx="100"
            cy="100"
            r="80"
            fill="none"
            stroke={isLoading ? "var(--muted-foreground)" : "var(--primary)"}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={isLoading ? circumference : strokeDashoffset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>

        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {isLoading ? (
            <div className="flex flex-col items-center gap-2">
              <svg className="h-8 w-8 animate-spin text-[var(--primary)]" viewBox="0 0 24 24" fill="none">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              <span className="text-sm text-[var(--muted-foreground)]">Analyzing...</span>
            </div>
          ) : (
            <>
              <span className="font-mono text-4xl font-bold text-[var(--foreground)]">
                {percentage}%
              </span>
              <span className="text-sm text-[var(--muted-foreground)]">
                Probability
              </span>
            </>
          )}
        </div>
      </div>

      {/* Podium badge */}
      {!isLoading && result && (
        <div
          className={`
            rounded-full px-6 py-2 text-sm font-semibold
            ${
              result.podium_likely
                ? "bg-green-900/30 text-green-400 border border-green-700"
                : "bg-amber-900/30 text-amber-400 border border-amber-700"
            }
          `}
        >
          {result.podium_likely ? "Likely Podium" : "Unlikely Podium"}
        </div>
      )}
    </div>
  );
}
