// src/pages/Login.tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

export default function Login() {
  const [pin, setPin] = useState<string | null>(null);
  const [pinId, setPinId] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const navigate = useNavigate();

  // Step 1: Get PIN from backend
  useEffect(() => {
    fetch("/api/auth/initiate")
      .then((res) => res.json())
      .then((data) => {
        console.log("🔥 INITIATE RESPONSE", data);
        setPin(data.code);
        setPinId(data.pin_id);
        setPolling(true);
      });
  }, []);

  // Step 2: Poll Plex to check if user completed PIN entry
  useEffect(() => {
    if (!polling || !pinId) return;
  
    const interval = setInterval(() => {
      fetch(`/api/auth/status/${pinId}`)
        .then((res) => res.json())
        .then((data) => {
          console.log("🛰️ Poll response:", data);
          if (data.authenticated) {
            clearInterval(interval);
            navigate("/recs");
          }
        });
    }, 10000);
  
    return () => clearInterval(interval);
  }, [polling, pinId, navigate]);

  return (
    <div className="flex flex-col items-center mt-20 text-center space-y-6">
      <h1 className="text-3xl font-bold">Welcome to PlexIntel</h1>
      {pin ? (
        <>
          <p className="text-lg">
            In order to retrieve your predictions, you need to 1. Know your Plex login 2. Copy the 4 digit code below then 3. Go to{" "}
            <a
              href="https://plex.tv/link"
              target="_blank"
              className="text-blue-500 underline"
              rel="noreferrer"
            >
              plex.tv/link
            </a>{" "}
            and enter this code:
          </p>
          <div className="text-5xl font-mono tracking-widest bg-gray-100 px-8 py-4 rounded-lg shadow-md">
            {pin}
          </div>
          <p className="text-sm text-gray-500">Once you do that with Plex, we will be waiting for you back here to complete login and show you your results...</p>
        </>
      ) : (
        <p>🔄 Generating login code...</p>
      )}
    </div>
  );
}
