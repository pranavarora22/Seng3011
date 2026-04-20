import { capitaliseDiseaseName } from "../../utils/formatters";

export default function Topbar({ title, subtitle, disease, countryCode }) {
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
        <div className="avatar-chip">T18 Charlie</div>
      </div>
    </header>
  );
}