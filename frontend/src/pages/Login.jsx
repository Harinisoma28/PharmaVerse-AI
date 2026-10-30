import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { LockKeyhole, ShieldCheck } from "lucide-react";

import { getStoredUser, login } from "../services/authService";
import { extractErrorMessage } from "../utils/error";

function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const isAuthenticated = Boolean(
    localStorage.getItem("access_token") && getStoredUser(),
  );

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      await login(email, password);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(extractErrorMessage(err, "Unable to sign in. Check your credentials and try again."));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <main className="min-h-screen bg-[#f7f8fa] px-4 py-8 text-[#102a43] sm:px-8 lg:px-12">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl items-center gap-10 lg:grid-cols-[1fr_420px]">
        <section className="hidden rounded-2xl bg-[#102a43] p-10 text-white shadow-lg lg:block">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#5a1725]">
            <ShieldCheck size={24} />
          </div>

          <p className="mt-8 text-xs font-bold uppercase tracking-[0.18em] text-rose-200">
            Intelligent pharmaceutical supply chain
          </p>

          <h1 className="mt-3 text-4xl font-bold tracking-tight">
            Trusted traceability for modern medicine.
          </h1>

          <p className="mt-5 max-w-lg text-sm leading-7 text-slate-300">
            PharmaVerse AI brings pharmaceutical identity, supply-chain
            monitoring, and verification workflows into one focused platform.
          </p>
        </section>

        <section className="w-full rounded-2xl border border-slate-200 bg-white p-7 shadow-lg sm:p-8">
          <div className="mb-8">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#5a1725] text-white lg:hidden">
              <ShieldCheck size={23} />
            </div>

            <p className="mt-6 text-xs font-bold uppercase tracking-[0.16em] text-[#5a1725]">
              PharmaVerse AI
            </p>

            <h1 className="mt-2 text-3xl font-bold tracking-tight text-[#102a43]">
              Sign in to the platform
            </h1>

            <p className="mt-3 text-sm leading-6 text-slate-600">
              Access pharmaceutical traceability and monitoring tools.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Email</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="username"
                placeholder="Enter your email"
                className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-[#102a43] outline-none transition placeholder:text-slate-400 focus:border-[#5a1725] focus:ring-2 focus:ring-[#5a1725]/10"
                required
              />
            </label>

            <label className="block">
              <span className="text-sm font-medium text-slate-700">Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                placeholder="Enter your password"
                className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-[#102a43] outline-none transition placeholder:text-slate-400 focus:border-[#5a1725] focus:ring-2 focus:ring-[#5a1725]/10"
                required
              />
            </label>

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#5a1725] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#43111c] disabled:cursor-not-allowed disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-[#5a1725]/30 focus:ring-offset-2"
            >
              <LockKeyhole size={17} />
              {isSubmitting ? "Signing in..." : "Continue to dashboard"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}

export default Login;
