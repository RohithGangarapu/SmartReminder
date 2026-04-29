import { useEffect, useState } from "react";
import { apiRequest, buildAuthHeaders } from "./api";

const SESSION_KEY = "smartreminder.session";

const emptyTaskForm = {
  title: "",
  description: "",
  datetime: "",
  source: "manual",
  status: "pending"
};

const emptyExtract = {
  text: ""
};

const emptyAuth = {
  username: "",
  email: "",
  password: ""
};

const emptyGoogleConnect = {
  authorization_code: "",
  redirect_uri: ""
};

const emptyGmailConnect = {
  authorization_code: "",
  redirect_uri: ""
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
  const [tasks, setTasks] = useState([]);
  const [taskForm, setTaskForm] = useState(emptyTaskForm);
  const [editingTaskId, setEditingTaskId] = useState(null);
  const [extractForm, setExtractForm] = useState(emptyExtract);
  const [googleForm, setGoogleForm] = useState(emptyGoogleConnect);
  const [gmailForm, setGmailForm] = useState(emptyGmailConnect);
  const [whatsappForm, setWhatsappForm] = useState(emptyWhatsappConnect);
  const [gmailFetchCount, setGmailFetchCount] = useState(10);
  const [whatsappFetchCount, setWhatsappFetchCount] = useState(20);
  const [activity, setActivity] = useState({
    type: "info",
    text: "Sign in to manage tasks and sync them to Google Calendar."
  });
  const [loading, setLoading] = useState({
    auth: false,
    tasks: false,
    taskSave: false,
    ai: false,
    google: false,
    gmail: false,
    whatsapp: false,
    bulkSync: false
  });

  useEffect(() => {
    saveSession(session);
  }, [session]);

  useEffect(() => {
    if (session?.access_token) {
      fetchTasks();
    } else {
      setTasks([]);
    }
  }, [session?.access_token]);

  async function fetchTasks() {
    if (!session?.access_token) {
      return;
    }

    setLoading((current) => ({ ...current, tasks: true }));
    try {
      const data = await apiRequest("/api/tasks", {
        headers: {
          ...buildAuthHeaders(session.access_token)
        }
      });
      setTasks(Array.isArray(data) ? data : []);
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, tasks: false }));
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
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });
      setSession(data);
      setActivity({
        type: "success",
        text: `Welcome ${data.username}. Your workspace is ready.`
      });
      setAuthForm(emptyAuth);
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, auth: false }));
    }
  }

  function handleLogout() {
    setSession(null);
    setEditingTaskId(null);
    setTaskForm(emptyTaskForm);
    setActivity({ type: "info", text: "You have been signed out." });
  }

  async function handleTaskSubmit(event) {
    event.preventDefault();
    if (!session?.access_token) {
      setActivity({ type: "error", text: "Please sign in first." });
      return;
    }

    setLoading((current) => ({ ...current, taskSave: true }));
    const path = editingTaskId ? `/api/tasks/${editingTaskId}` : "/api/tasks";
    const method = editingTaskId ? "PUT" : "POST";

    try {
      await apiRequest(path, {
        method,
        headers: {
          "Content-Type": "application/json",
          ...buildAuthHeaders(session.access_token)
        },
        body: JSON.stringify(taskForm)
      });
      setActivity({
        type: "success",
        text: editingTaskId ? "Task updated." : "Task created."
      });
      setTaskForm(emptyTaskForm);
      setEditingTaskId(null);
      fetchTasks();
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, taskSave: false }));
    }
  }

  function handleTaskEdit(task) {
    setEditingTaskId(task.id);
    setTaskForm({
      title: task.title || "",
      description: task.description || "",
      datetime: (task.datetime || "").slice(0, 16),
      source: task.source || "manual",
      status: task.status || "pending"
    });
  }

  async function handleTaskDelete(taskId) {
    if (!session?.access_token) {
      return;
    }

    try {
      await apiRequest(`/api/tasks/${taskId}`, {
        method: "DELETE",
        headers: buildAuthHeaders(session.access_token)
      });
      setActivity({ type: "success", text: "Task deleted." });
      if (editingTaskId === taskId) {
        setEditingTaskId(null);
        setTaskForm(emptyTaskForm);
      }
      fetchTasks();
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    }
  }

  async function handleExtract(event) {
    event.preventDefault();
    setLoading((current) => ({ ...current, ai: true }));

    try {
      const data = await apiRequest("/api/ai/extract-task", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(extractForm)
      });
      setTaskForm((current) => ({
        ...current,
        title: data.title || current.title,
        datetime: data.datetime || current.datetime
      }));
      setActivity({
        type: "success",
        text: "AI extracted a task draft and filled the task form."
      });
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, ai: false }));
    }
  }

  async function handleGoogleConnect(event) {
    event.preventDefault();
    if (!session?.access_token) {
      return;
    }

    setLoading((current) => ({ ...current, google: true }));
    try {
      const data = await apiRequest("/api/integrations/google-calendar/connect", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildAuthHeaders(session.access_token)
        },
        body: JSON.stringify(googleForm)
      });
      setActivity({
        type: "success",
        text: `Google Calendar connected for ${data.google_email}.`
      });
      setGoogleForm(emptyGoogleConnect);
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, google: false }));
    }
  }

  async function handleGmailConnect(event) {
    event.preventDefault();
    if (!session?.access_token) {
      return;
    }

    setLoading((current) => ({ ...current, gmail: true }));
    try {
      const data = await apiRequest("/api/integrations/gmail/connect", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildAuthHeaders(session.access_token)
        },
        body: JSON.stringify(gmailForm)
      });
      setActivity({
        type: "success",
        text: `Gmail connected for ${data.gmail_email}.`
      });
      setGmailForm(emptyGmailConnect);
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, gmail: false }));
    }
  }

  async function handleGmailFetch() {
    if (!session?.access_token) {
      return;
    }

    setLoading((current) => ({ ...current, gmail: true }));
    try {
      const data = await apiRequest(`/api/integrations/gmail/fetch?max_results=${gmailFetchCount}`, {
        headers: buildAuthHeaders(session.access_token)
      });
      setActivity({
        type: "success",
        text: `Gmail fetched: ${data.fetched}, created tasks: ${data.created}, skipped: ${data.skipped}.`
      });
      fetchTasks();
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, gmail: false }));
    }
  }

  async function handleWhatsappConnect(event) {
    event.preventDefault();
    if (!session?.access_token) {
      return;
    }

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
      setActivity({
        type: "success",
        text: `WhatsApp connected for phone id ${data.phone_number_id}.`
      });
      setWhatsappForm(emptyWhatsappConnect);
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, whatsapp: false }));
    }
  }

  async function handleWhatsappFetch() {
    if (!session?.access_token) {
      return;
    }

    setLoading((current) => ({ ...current, whatsapp: true }));
    try {
      const data = await apiRequest(`/api/integrations/whatsapp/fetch?limit=${whatsappFetchCount}`, {
        headers: buildAuthHeaders(session.access_token)
      });
      setActivity({
        type: "success",
        text: `WhatsApp fetched: ${data.fetched}, created tasks: ${data.created}, skipped: ${data.skipped}.`
      });
      fetchTasks();
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, whatsapp: false }));
    }
  }

  async function handleSyncTask(taskId) {
    if (!session?.access_token) {
      return;
    }

    try {
      const data = await apiRequest(`/api/integrations/google-calendar/sync-task/${taskId}`, {
        method: "POST",
        headers: buildAuthHeaders(session.access_token)
      });
      setActivity({
        type: "success",
        text: `Task synced to calendar: ${data.title || "Task"}.`
      });
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    }
  }

  async function handleBulkSync() {
    if (!session?.access_token) {
      return;
    }

    setLoading((current) => ({ ...current, bulkSync: true }));
    try {
      const data = await apiRequest("/api/integrations/google-calendar/sync-tasks", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildAuthHeaders(session.access_token)
        },
        body: JSON.stringify({
          calendar_id: "primary"
        })
      });
      setActivity({
        type: "success",
        text: `Calendar sync finished. Synced ${data.synced} of ${data.total} tasks.`
      });
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    } finally {
      setLoading((current) => ({ ...current, bulkSync: false }));
    }
  }

  async function handleUnsyncTask(taskId) {
    if (!session?.access_token) {
      return;
    }

    try {
      await apiRequest(`/api/integrations/google-calendar/sync-task/${taskId}/remove`, {
        method: "DELETE",
        headers: buildAuthHeaders(session.access_token)
      });
      setActivity({
        type: "success",
        text: "Calendar event removed for this task."
      });
    } catch (error) {
      setActivity({ type: "error", text: error.message });
    }
  }

  const pendingTasks = tasks.filter((task) => task.status !== "done").length;

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">SmartReminder</p>
          <h1>Simple task capture, sync, and reminder management.</h1>
          <p className="hero-copy">
            This frontend is built around your current backend APIs. It gives you
            one place to sign in, create tasks, extract tasks from text, and push
            them into Google Calendar.
          </p>
        </div>
        <div className="hero-panel">
          <div className="stat-grid">
            <article className="stat-card">
              <span className="stat-label">Total tasks</span>
              <strong>{tasks.length}</strong>
            </article>
            <article className="stat-card">
              <span className="stat-label">Open tasks</span>
              <strong>{pendingTasks}</strong>
            </article>
            <article className="stat-card">
              <span className="stat-label">Signed in</span>
              <strong>{session ? "Yes" : "No"}</strong>
            </article>
          </div>
          {session ? (
            <div className="session-strip">
              <span>{session.username}</span>
              <button className="ghost-button" onClick={handleLogout}>
                Logout
              </button>
            </div>
          ) : (
            <p className="mini-note">Use register once, then login anytime.</p>
          )}
        </div>
      </header>

      <div className={`notice notice-${activity.type}`}>{activity.text}</div>

      <main className="dashboard">
        <section className="card auth-card">
          <div className="card-head">
            <div>
              <p className="section-tag">Access</p>
              <h2>{authMode === "login" ? "Login" : "Create account"}</h2>
            </div>
            <div className="tab-row">
              <button
                className={authMode === "login" ? "tab active" : "tab"}
                onClick={() => setAuthMode("login")}
                type="button"
              >
                Login
              </button>
              <button
                className={authMode === "register" ? "tab active" : "tab"}
                onClick={() => setAuthMode("register")}
                type="button"
              >
                Register
              </button>
            </div>
          </div>

          <form className="stack-form" onSubmit={handleAuthSubmit}>
            <label>
              <span>Username</span>
              <input
                value={authForm.username}
                onChange={(event) =>
                  setAuthForm((current) => ({ ...current, username: event.target.value }))
                }
                placeholder="rohith"
                required={authMode === "register"}
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
                placeholder="rohith@example.com"
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
                placeholder="Minimum 8 characters"
                required
              />
            </label>
            <button className="primary-button" disabled={loading.auth} type="submit">
              {loading.auth ? "Please wait..." : authMode === "login" ? "Login" : "Register"}
            </button>
          </form>
        </section>

        <section className="card">
          <div className="card-head">
            <div>
              <p className="section-tag">AI helper</p>
              <h2>Extract a task from natural language</h2>
            </div>
          </div>
          <form className="stack-form" onSubmit={handleExtract}>
            <label>
              <span>Message or reminder text</span>
              <textarea
                rows="5"
                value={extractForm.text}
                onChange={(event) =>
                  setExtractForm({ text: event.target.value })
                }
                placeholder="Example: remind me tomorrow at 9am to call the vendor"
              />
            </label>
            <button className="secondary-button" disabled={loading.ai} type="submit">
              {loading.ai ? "Extracting..." : "Extract task draft"}
            </button>
          </form>
        </section>

        <section className="card wide-card">
          <div className="card-head">
            <div>
              <p className="section-tag">Tasks</p>
              <h2>{editingTaskId ? "Edit task" : "Create task"}</h2>
            </div>
            <button className="ghost-button" onClick={fetchTasks} type="button">
              Refresh list
            </button>
          </div>
          <form className="task-form-grid" onSubmit={handleTaskSubmit}>
            <label>
              <span>Title</span>
              <input
                value={taskForm.title}
                onChange={(event) =>
                  setTaskForm((current) => ({ ...current, title: event.target.value }))
                }
                placeholder="Pay electricity bill"
                required
              />
            </label>
            <label>
              <span>Date and time</span>
              <input
                type="datetime-local"
                value={taskForm.datetime}
                onChange={(event) =>
                  setTaskForm((current) => ({ ...current, datetime: event.target.value }))
                }
                required
              />
            </label>
            <label>
              <span>Source</span>
              <select
                value={taskForm.source}
                onChange={(event) =>
                  setTaskForm((current) => ({ ...current, source: event.target.value }))
                }
              >
                <option value="manual">manual</option>
                <option value="gmail">gmail</option>
                <option value="whatsapp">whatsapp</option>
              </select>
            </label>
            <label>
              <span>Status</span>
              <select
                value={taskForm.status}
                onChange={(event) =>
                  setTaskForm((current) => ({ ...current, status: event.target.value }))
                }
              >
                <option value="pending">pending</option>
                <option value="done">done</option>
              </select>
            </label>
            <label className="full-span">
              <span>Description</span>
              <textarea
                rows="4"
                value={taskForm.description}
                onChange={(event) =>
                  setTaskForm((current) => ({ ...current, description: event.target.value }))
                }
                placeholder="Optional details"
              />
            </label>
            <div className="button-row full-span">
              <button className="primary-button" disabled={loading.taskSave} type="submit">
                {loading.taskSave
                  ? "Saving..."
                  : editingTaskId
                    ? "Update task"
                    : "Create task"}
              </button>
              <button
                className="ghost-button"
                onClick={() => {
                  setEditingTaskId(null);
                  setTaskForm(emptyTaskForm);
                }}
                type="button"
              >
                Reset form
              </button>
              <button
                className="secondary-button"
                disabled={loading.bulkSync || !session}
                onClick={handleBulkSync}
                type="button"
              >
                {loading.bulkSync ? "Syncing..." : "Sync all to Google Calendar"}
              </button>
            </div>
          </form>

          <div className="task-list">
            {loading.tasks ? (
              <p className="empty-state">Loading tasks...</p>
            ) : tasks.length === 0 ? (
              <p className="empty-state">No tasks yet. Create one or import from Gmail or WhatsApp.</p>
            ) : (
              tasks.map((task) => (
                <article className="task-card" key={task.id}>
                  <div className="task-card-top">
                    <div>
                      <h3>{task.title}</h3>
                      <p>{task.description || "No description"}</p>
                    </div>
                    <span className={`badge badge-${task.status}`}>{task.status}</span>
                  </div>
                  <div className="task-meta">
                    <span>{formatDateTime(task.datetime)}</span>
                    <span>Source: {task.source}</span>
                  </div>
                  <div className="button-row">
                    <button className="ghost-button" onClick={() => handleTaskEdit(task)} type="button">
                      Edit
                    </button>
                    <button className="ghost-button" onClick={() => handleTaskDelete(task.id)} type="button">
                      Delete
                    </button>
                    <button className="secondary-button" onClick={() => handleSyncTask(task.id)} type="button">
                      Sync
                    </button>
                    <button className="ghost-button" onClick={() => handleUnsyncTask(task.id)} type="button">
                      Remove event
                    </button>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <div>
              <p className="section-tag">Google Calendar</p>
              <h2>Connect and sync</h2>
            </div>
          </div>
          <form className="stack-form" onSubmit={handleGoogleConnect}>
            <label>
              <span>Authorization code</span>
              <input
                value={googleForm.authorization_code}
                onChange={(event) =>
                  setGoogleForm((current) => ({
                    ...current,
                    authorization_code: event.target.value
                  }))
                }
                placeholder="Paste code from Google OAuth flow"
                required
              />
            </label>
            <label>
              <span>Redirect URI</span>
              <input
                value={googleForm.redirect_uri}
                onChange={(event) =>
                  setGoogleForm((current) => ({ ...current, redirect_uri: event.target.value }))
                }
                placeholder="http://localhost:5173/google/callback"
                required
              />
            </label>
            <button className="primary-button" disabled={loading.google} type="submit">
              {loading.google ? "Connecting..." : "Connect Google Calendar"}
            </button>
          </form>
          <p className="mini-note">
            Use Google scope <code>https://www.googleapis.com/auth/calendar.events</code>.
          </p>
        </section>

        <section className="card">
          <div className="card-head">
            <div>
              <p className="section-tag">Gmail</p>
              <h2>Connect and import</h2>
            </div>
          </div>
          <form className="stack-form" onSubmit={handleGmailConnect}>
            <label>
              <span>Authorization code</span>
              <input
                value={gmailForm.authorization_code}
                onChange={(event) =>
                  setGmailForm((current) => ({
                    ...current,
                    authorization_code: event.target.value
                  }))
                }
                placeholder="Paste code from Google OAuth flow"
                required
              />
            </label>
            <label>
              <span>Redirect URI</span>
              <input
                value={gmailForm.redirect_uri}
                onChange={(event) =>
                  setGmailForm((current) => ({ ...current, redirect_uri: event.target.value }))
                }
                placeholder="http://localhost:5173/gmail/callback"
                required
              />
            </label>
            <button className="primary-button" disabled={loading.gmail} type="submit">
              {loading.gmail ? "Connecting..." : "Connect Gmail"}
            </button>
          </form>
          <div className="inline-controls">
            <label>
              <span>Fetch count</span>
              <input
                type="number"
                min="1"
                max="50"
                value={gmailFetchCount}
                onChange={(event) => setGmailFetchCount(event.target.value)}
              />
            </label>
            <button className="secondary-button" disabled={loading.gmail} onClick={handleGmailFetch} type="button">
              Fetch Gmail tasks
            </button>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <div>
              <p className="section-tag">WhatsApp</p>
              <h2>Connect and review</h2>
            </div>
          </div>
          <form className="stack-form" onSubmit={handleWhatsappConnect}>
            <label>
              <span>Phone number id</span>
              <input
                value={whatsappForm.phone_number_id}
                onChange={(event) =>
                  setWhatsappForm((current) => ({
                    ...current,
                    phone_number_id: event.target.value
                  }))
                }
                placeholder="Meta phone_number_id"
                required
              />
            </label>
            <label>
              <span>Business phone number</span>
              <input
                value={whatsappForm.business_phone_number}
                onChange={(event) =>
                  setWhatsappForm((current) => ({
                    ...current,
                    business_phone_number: event.target.value
                  }))
                }
                placeholder="+91..."
              />
            </label>
            <button className="primary-button" disabled={loading.whatsapp} type="submit">
              {loading.whatsapp ? "Connecting..." : "Connect WhatsApp"}
            </button>
          </form>
          <div className="inline-controls">
            <label>
              <span>Fetch count</span>
              <input
                type="number"
                min="1"
                max="100"
                value={whatsappFetchCount}
                onChange={(event) => setWhatsappFetchCount(event.target.value)}
              />
            </label>
            <button
              className="secondary-button"
              disabled={loading.whatsapp}
              onClick={handleWhatsappFetch}
              type="button"
            >
              Fetch WhatsApp tasks
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
