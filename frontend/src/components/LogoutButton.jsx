import { supabase } from "../lib/supabase";
import { useNavigate } from "react-router-dom";

function LogoutButton() {
  const navigate = useNavigate();

  async function logout() {
    await supabase.auth.signOut();

    alert("Logged Out");
    navigate("/login");
  }

  return (
    <button onClick={logout}>
      Logout
    </button>
  );
}

export default LogoutButton;
