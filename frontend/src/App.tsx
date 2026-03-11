import { BrowserRouter, Routes, Route } from "react-router-dom";
import Login from "./pages/Login";
import Welcome from "./pages/Welcome";
import PostLogin from "./pages/PostLogin";
import Admin from "./pages/Admin";
import AdminSettings from "./pages/AdminSettings";
import Recommendations from "./components/Recommendations";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/welcome" element={<Welcome />} />
        <Route path="/post-login" element={<PostLogin />} />
        <Route path="/recs" element={<Recommendations />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/admin/settings" element={<AdminSettings />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
