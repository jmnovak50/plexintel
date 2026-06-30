import { NavLink } from 'react-router-dom';

const ADMIN_NAV_ITEMS = [
  { to: '/recs', label: 'Recommendations', end: false },
  { to: '/admin', label: 'Persona View', end: true },
  { to: '/admin/pipeline', label: 'Pipeline runs', end: false },
  { to: '/admin/digest', label: 'Digest Studio', end: false },
  { to: '/admin/settings', label: 'Settings', end: false },
] as const;

function navClassName(isActive: boolean) {
  return isActive ? 'recs-view-pill-active' : 'recs-view-pill-inactive';
}

export default function AdminNav() {
  return (
    <nav aria-label="Admin navigation" className="flex flex-wrap items-center gap-2">
      {ADMIN_NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => navClassName(isActive)}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
