"use client";

import { FormEvent, useState } from "react";

interface Options {
  drivers: string[];
  constructors: string[];
  circuits: string[];
  seasons: number[];
}

interface PredictionFormProps {
  options: Options | undefined;
  isLoading: boolean;
  isSubmitting: boolean;
  onSubmit: (data: {
    grid: number;
    driver: string;
    constructor: string;
    circuit: string;
    season: number;
  }) => void;
}

export function PredictionForm({
  options,
  isLoading,
  isSubmitting,
  onSubmit,
}: PredictionFormProps) {
  const [grid, setGrid] = useState<number>(1);
  const [driver, setDriver] = useState<string>("");
  const [constructor, setConstructor] = useState<string>("");
  const [circuit, setCircuit] = useState<string>("");
  const [season, setSeason] = useState<number | "">("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!driver || !constructor || !circuit || !season) return;

    onSubmit({
      grid,
      driver,
      constructor,
      circuit,
      season: Number(season),
    });
  };

  const selectClassName = `
    w-full rounded-lg border border-[var(--border)] bg-[var(--input)] 
    px-4 py-3 text-[var(--foreground)] 
    focus:border-[var(--primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/20
    disabled:cursor-not-allowed disabled:opacity-50
    appearance-none cursor-pointer
  `;

  const labelClassName = "mb-2 block text-sm font-medium text-[var(--muted-foreground)]";

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <label htmlFor="grid" className={labelClassName}>
            Grid Position
          </label>
          <input
            type="number"
            id="grid"
            min={1}
            max={20}
            value={grid}
            onChange={(e) => setGrid(Number(e.target.value))}
            disabled={isSubmitting}
            className={`
              w-full rounded-lg border border-[var(--border)] bg-[var(--input)] 
              px-4 py-3 text-[var(--foreground)] 
              focus:border-[var(--primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/20
              disabled:cursor-not-allowed disabled:opacity-50
            `}
          />
        </div>

        <div>
          <label htmlFor="season" className={labelClassName}>
            Season
          </label>
          <div className="relative">
            <select
              id="season"
              value={season}
              onChange={(e) => setSeason(Number(e.target.value))}
              disabled={isLoading || isSubmitting}
              className={selectClassName}
            >
              <option value="">Select season</option>
              {options?.seasons.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <ChevronIcon />
          </div>
        </div>
      </div>

      <div>
        <label htmlFor="driver" className={labelClassName}>
          Driver
        </label>
        <div className="relative">
          <select
            id="driver"
            value={driver}
            onChange={(e) => setDriver(e.target.value)}
            disabled={isLoading || isSubmitting}
            className={selectClassName}
          >
            <option value="">Select driver</option>
            {options?.drivers.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <ChevronIcon />
        </div>
      </div>

      <div>
        <label htmlFor="team" className={labelClassName}>
          Team
        </label>
        <div className="relative">
          <select
            id="team"
            value={constructor}
            onChange={(e) => setConstructor(e.target.value)}
            disabled={isLoading || isSubmitting}
            className={selectClassName}
          >
            <option value="">Select team</option>
            {options?.constructors.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <ChevronIcon />
        </div>
      </div>

      <div>
        <label htmlFor="circuit" className={labelClassName}>
          Circuit
        </label>
        <div className="relative">
          <select
            id="circuit"
            value={circuit}
            onChange={(e) => setCircuit(e.target.value)}
            disabled={isLoading || isSubmitting}
            className={selectClassName}
          >
            <option value="">Select circuit</option>
            {options?.circuits.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <ChevronIcon />
        </div>
      </div>

      <button
        type="submit"
        disabled={isLoading || isSubmitting || !driver || !constructor || !circuit || !season}
        className={`
          w-full rounded-lg bg-[var(--primary)] py-4 font-semibold text-[var(--primary-foreground)]
          transition-all hover:bg-[#c00500] 
          disabled:cursor-not-allowed disabled:opacity-50
          focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:ring-offset-2 focus:ring-offset-[var(--card)]
        `}
      >
        {isSubmitting ? (
          <span className="flex items-center justify-center gap-2">
            <LoadingSpinner />
            Predicting...
          </span>
        ) : (
          "Predict Podium"
        )}
      </button>
    </form>
  );
}

function ChevronIcon() {
  return (
    <svg
      className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted-foreground)]"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  );
}

function LoadingSpinner() {
  return (
    <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
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
  );
}
