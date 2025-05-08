// src/pages/Welcome.tsx
import { useSearchParams, useNavigate } from "react-router-dom";
import { useEffect } from "react";

export default function Welcome() {
  const [params] = useSearchParams();
  const username = params.get("user");
  const navigate = useNavigate();

  useEffect(() => {
    if (username) {
      // Store username locally
      localStorage.setItem("plex_user", username);
      // Redirect to recs page after 1 second
      setTimeout(() => {
        navigate("/recs");
      }, 1000);
    }
  }, [username, navigate]);

  return (
    <div className="flex flex-col items-center mt-20">
      <h1 className="text-2xl font-bold">Welcome, {username}!</h1>
      <p className="text-gray-500">Logging you in...</p>
    </div>
  );
}
