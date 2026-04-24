import { capitaliseDiseaseName } from "../../utils/formatters";

export default function Topbar({ title, subtitle, disease, countryCode, currentUser, onLogout }) {
  return (
    <header className="topbar">
      <div>
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </div>

      <div className="topbar-meta">
        <div className="topbar-pill">
          {capitaliseDiseaseName(disease)} · {countryCode}
        </div>
        {currentUser && (
          <div className="topbar-user">
            <span className="avatar-chip">
              {currentUser.name ? currentUser.name.charAt(0).toUpperCase() : currentUser.email.charAt(0).toUpperCase()}
            </span>
            <span className="topbar-username">{currentUser.name || currentUser.email}</span>
            <button className="topbar-logout-btn" onClick={onLogout} title="Sign out">
              Sign out
            </button>
          </div>
        )}
        {!currentUser && <div className="avatar-chip">T18 Charlie</div>}
      </div>
    </header>
  );
}
