import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

function PostLogin() {
  const location = useLocation();
  const navigate = useNavigate();
  const [code, setCode] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const pinId = params.get("pin_id");
    if (!pinId) return;

    // Fetch the code to show user
    fetch(`/api/auth/initiate?pin_id=${pinId}`)
      .then(res => res.json())
      .then(data => {
        setCode(data.code);
      });

    const interval = setInterval(async () => {
      const res = await fetch(`/api/auth/status/${pinId}`);
      if (res.ok) {
        const data = await res.json();
        if (data?.user_id) {
          clearInterval(interval);
          navigate("/"); // or "/recs"
        }
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [location, navigate]);

  return (
    <div className="p-6 text-center">
      <h1 className="text-2xl font-bold mb-4">🔄 Waiting for Plex login...</h1>
      <p className="mb-2 text-gray-600">To complete login, go to:</p>
      <p className="mb-4 text-lg font-mono bg-gray-100 inline-block px-4 py-2 rounded shadow">
        https://plex.tv/link
      </p>
      {code && (
        <>
          <p className="text-gray-600 mb-1">And enter this code:</p>
          <div className="text-3xl font-bold tracking-widest">{code}</div>
        </>
      )}
    </div>
  );
}

export default PostLogin;
