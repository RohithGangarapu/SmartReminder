import { useEffect, useMemo, useState } from "react";
import { apiRequest, buildAuthHeaders } from "./api";

const SESSION_KEY = "smartreminder.session";

const emptyAuth = {
  username: "",
  email: "",
  password: ""
};

const emptyWhatsappConnect = {
  phone_number_id: "",
  business_phone_number: ""
};

function loadSession() {
  const raw = window.localStorage.getItem(SESSION_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveSession(session) {
  if (!session) {
    window.localStorage.removeItem(SESSION_KEY);
    return;
  }
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

function formatDateTime(value) {
  if (!value) {
    return "No date";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function App() {
  const [session, setSession] = useState(() => loadSession());
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState(emptyAuth);
  const [whatsappForm, setWhatsappForm] = useState(emptyWhatsappConnect);
  const [tasks, setTasks] = useState([]);
  const [integrationStatus, setIntegrationStatus] = useState(null);
  const [activity, setActivity] = useState({ type: "info", text: "Please login." });
  const [loading, setLoading] = useState({
    auth: false,
    tasks: false,
    gmail: false,
    whatsapp: false,
    syncNow: false
  });

  useEffect(() => {
    saveSession(session);
  }, [session]);

  useEffect(() => {
    if (!session?.access_token) {
      setTasks([]);
      setIntegrationStatus(null);
      return;
    }
    fetchTasks();
    fetchIntegrationStatus();
  }, [session?.access_token]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthStatus = params.get("google_oauth");
    if (oauthStatus === "success") {
      setActivity({ type: "success", text: "Google integrated successfully." });
      fetchIntegrationStatus();
      params.delete("google_oauth");
      params.delete("reason");
      const clean = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}`;
      window.history.replaceState({}, "", clean);
    } else if (oauthStatus === "error") {
      const reason = params.get("reason") || "OAuth failed";
      setActivity({ type: "error", text: `Google integration failed: ${reason}` });
    }
  }, []);

  const sortedTasks = useMemo(
    () => [...tasks].sort((a, b) => new Date(a.datetime) - new Date(b.datetime)),
    [tasks]
  );

  async function fetchTasks() {
    if (!session?.access_token) return;
    setLoading((current) => ({ ...current, tasks: true }));
    try {
      const data = await apiRequest("/api/tasks", {
        headers: buildAuthHeaders(session.access_token)
      });
      setTasks(Array.isArray(data) ? data : []);
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, tasks: false }));
    }
  }

  async function fetchIntegrationStatus() {
    if (!session?.access_token) return;
    try {
      const data = await apiRequest("/api/integrations/status", {
        headers: buildAuthHeaders(session.access_token)
      });
      setIntegrationStatus(data);
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    }
  }

  async function handleAuthSubmit(event) {
    event.preventDefault();
    setLoading((current) => ({ ...current, auth: true }));

    const path = authMode === "register" ? "/api/auth/register" : "/api/auth/login";
    const payload =
      authMode === "register"
        ? authForm
        : {
            username: authForm.username,
            email: authForm.email,
            password: authForm.password
          };

    try {
      const data = await apiRequest(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      setSession(data);
      setAuthForm(emptyAuth);
      setActivity({ type: "success", text: `Welcome ${data.username}.` });
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, auth: false }));
    }
  }

  function handleLogout() {
    setSession(null);
    setActivity({ type: "info", text: "Logged out." });
  }

  async function handleGoogleIntegrate() {
    if (!session?.access_token) return;

    setLoading((current) => ({ ...current, gmail: true }));
    try {
      const data = await apiRequest("/api/integrations/google/start", {
        headers: buildAuthHeaders(session.access_token)
      });
      if (!data?.auth_url) {
        throw new Error("OAuth URL not received");
      }
      window.location.href = data.auth_url;
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, gmail: false }));
    }
  }

  async function handleWhatsappConnect(event) {
    event.preventDefault();
    if (!session?.access_token) return;

    setLoading((current) => ({ ...current, whatsapp: true }));
    try {
      const data = await apiRequest("/api/integrations/whatsapp/connect", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildAuthHeaders(session.access_token)
        },
        body: JSON.stringify(whatsappForm)
      });
      setWhatsappForm(emptyWhatsappConnect);
      setActivity({ type: "success", text: `WhatsApp connected: ${data.phone_number_id}` });
      fetchIntegrationStatus();
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, whatsapp: false }));
    }
  }

  async function handleSyncNow() {
    if (!session?.access_token) return;
    setLoading((current) => ({ ...current, syncNow: true }));
    try {
      const data = await apiRequest("/api/integrations/sync-now", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildAuthHeaders(session.access_token)
        },
        body: JSON.stringify({ calendar_id: "primary", gmail_max_results: 10 })
      });
      const gmailCreated = data?.gmail?.created ?? 0;
      const calendarSynced = data?.google_calendar?.synced ?? 0;
      setActivity({
        type: "success",
        text: `Sync complete. Gmail created ${gmailCreated}, calendar synced ${calendarSynced}.`
      });
      fetchTasks();
      fetchIntegrationStatus();
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, syncNow: false }));
    }
  }

  if (!session?.access_token) {
    return (
      <div className="auth-page">
        <section className="auth-card">
          <h1>SmartReminder</h1>
          <p className="subtext">Login to view your scheduled tasks dashboard.</p>

          <div className="tab-row">
            <button
              className={authMode === "login" ? "tab active" : "tab"}
              type="button"
              onClick={() => setAuthMode("login")}
            >
              Login
            </button>
            <button
              className={authMode === "register" ? "tab active" : "tab"}
              type="button"
              onClick={() => setAuthMode("register")}
            >
              Register
            </button>
          </div>

          <form className="stack-form" onSubmit={handleAuthSubmit}>
            <label>
              <span>Username</span>
              <input
                value={authForm.username}
                onChange={(event) =>
                  setAuthForm((current) => ({ ...current, username: event.target.value }))
                }
                required
              />
            </label>
            <label>
              <span>Email</span>
              <input
                type="email"
                value={authForm.email}
                onChange={(event) =>
                  setAuthForm((current) => ({ ...current, email: event.target.value }))
                }
              />
            </label>
            <label>
              <span>Password</span>
              <input
                type="password"
                value={authForm.password}
                onChange={(event) =>
                  setAuthForm((current) => ({ ...current, password: event.target.value }))
                }
                required
              />
            </label>
            <button className="primary-button" disabled={loading.auth} type="submit">
              {loading.auth ? "Please wait..." : authMode === "login" ? "Login" : "Register"}
            </button>
          </form>

          <p className={`notice notice-${activity.type}`}>{activity.text}</p>
        </section>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <header className="topbar">
        <div>
          <h1>Scheduled Tasks</h1>
          <p className="subtext">{session.username}</p>
        </div>
        <div className="button-row">
          <button className="secondary-button" onClick={handleSyncNow} disabled={loading.syncNow} type="button">
            {loading.syncNow ? "Syncing..." : "Sync"}
          </button>
          <button className="ghost-button" onClick={handleLogout} type="button">
            Logout
          </button>
        </div>
      </header>

      <section className="status-row">
        <article className="status-card">
          <span>Gmail</span>
          <strong className={integrationStatus?.gmail_connected ? "on" : "off"}>
            {integrationStatus?.gmail_connected ? "Active" : "Inactive"}
          </strong>
        </article>
        <article className="status-card">
          <span>WhatsApp</span>
          <strong className={integrationStatus?.whatsapp_connected ? "on" : "off"}>
            {integrationStatus?.whatsapp_connected ? "Active" : "Inactive"}
          </strong>
        </article>
      </section>

      <main className="tasks-center">
        {loading.tasks ? (
          <p className="subtext">Loading tasks...</p>
        ) : sortedTasks.length === 0 ? (
          <p className="subtext">No scheduled tasks yet.</p>
        ) : (
          sortedTasks.map((task) => (
            <article className="task-card" key={task.id}>
              <div className="task-head">
                <h3>{task.title}</h3>
                <span className={`badge badge-${task.status}`}>{task.status}</span>
              </div>
              <p>{task.description || "No description"}</p>
              <div className="task-meta">
                <span>{formatDateTime(task.datetime)}</span>
                <span>{task.source}</span>
              </div>
            </article>
          ))
        )}
      </main>

      <section className="settings-panel">
        <h2>Settings</h2>
        <p className="subtext">Connect integrations below.</p>

        <div className="settings-grid">
          <div className="stack-form">
            <h3>Integrate Google</h3>
            <p className="subtext">Connect once to enable Gmail and Google Calendar.</p>
            <button className="primary-button" disabled={loading.gmail} onClick={handleGoogleIntegrate} type="button">
              {loading.gmail ? "Redirecting..." : "Integrate Google"}
            </button>
          </div>

          <form className="stack-form" onSubmit={handleWhatsappConnect}>
            <h3>Integrate WhatsApp</h3>
            <label>
              <span>Phone number id</span>
              <input
                value={whatsappForm.phone_number_id}
                onChange={(event) =>
                  setWhatsappForm((current) => ({ ...current, phone_number_id: event.target.value }))
                }
                required
              />
            </label>
            <label>
              <span>Business number</span>
              <input
                value={whatsappForm.business_phone_number}
                onChange={(event) =>
                  setWhatsappForm((current) => ({ ...current, business_phone_number: event.target.value }))
                }
              />
            </label>
            <button className="primary-button" disabled={loading.whatsapp} type="submit">
              {loading.whatsapp ? "Connecting..." : "Integrate WhatsApp"}
            </button>
          </form>
        </div>
      </section>

      <p className={`notice notice-${activity.type}`}>{activity.text}</p>
    </div>
  );
}

export default App;
