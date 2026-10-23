import {
  Link as RouterLink,
  useNavigate as useRouterNavigate,
} from "react-router-dom";
import { useCallback } from "react";

// Keep existing page links/bookmarks usable while presenting canonical area URLs.
export function legacyDestination(destination) {
  if (typeof destination === "object" && destination?.pathname)
    return {
      ...destination,
      pathname: legacyDestination(destination.pathname),
    };
  if (typeof destination !== "string" || !destination.startsWith("/"))
    return destination;
  const boundary = destination.search(/[?#]/);
  const path = boundary < 0 ? destination : destination.slice(0, boundary);
  const suffix = boundary < 0 ? "" : destination.slice(boundary);
  const exact = {
    "/": "/inbox",
    "/policies": "/policies/library",
    "/policies/traceability": "/policies",
    "/policies/new": "/policies/library/new",
  };
  if (exact[path]) return exact[path] + suffix;
  const prefixes = [
    ["/customers", "/inbox/customers"],
    ["/cases", "/inbox/cases"],
    ["/monitoring", "/inbox/transactions"],
    ["/rules", "/policies/controls"],
    ["/changes", "/policies/changes"],
    ["/agents", "/advanced/agents"],
    ["/audit", "/evidence"],
    ["/decisions", "/evidence/assessments"],
    ["/evaluate", "/evidence/evaluate"],
    ["/sources", "/settings/sources"],
    ["/external-data", "/settings/sources"],
    ["/assistant", "/policies/assistant"],
    ["/query", "/policies/assistant"],
  ];
  for (const [oldPath, nextPath] of prefixes) {
    if (path === oldPath || path.startsWith(oldPath + "/"))
      return nextPath + path.slice(oldPath.length) + suffix;
  }
  // Legacy policy editor, excluding canonical policy-area children.
  if (/^\/policies\/[^/]+\/edit$/.test(path))
    return "/policies/library" + path.slice("/policies".length) + suffix;
  return destination;
}

export function Link({ to, ...props }) {
  return <RouterLink {...props} to={legacyDestination(to)} />;
}
export function useNavigate() {
  const navigate = useRouterNavigate();
  return useCallback(
    (to, options) => navigate(legacyDestination(to), options),
    [navigate],
  );
}

export const AREAS = [
  {
    path: "/inbox",
    title: "Inbox",
    links: [
      ["/inbox", "Work queue"],
      ["/inbox/alerts", "Alerts"],
      ["/inbox/cases", "Cases"],
      ["/inbox/approvals", "Approvals"],
      ["/inbox/customers", "Customers"],
      ["/inbox/transactions", "Transactions"],
    ],
  },
  {
    path: "/policies",
    title: "Policies & Controls",
    links: [
      ["/policies", "Traceability"],
      ["/policies/library", "Policy library"],
      ["/policies/controls", "Controls"],
      ["/policies/changes", "Policy changes"],
      ["/policies/assistant", "Policy research"],
    ],
  },
  {
    path: "/evidence",
    title: "Evidence",
    links: [
      ["/evidence", "Packs & audit"],
      ["/evidence/assessments", "Assessment records"],
      ["/evidence/evaluate", "Prepare assessment"],
    ],
  },
  {
    path: "/settings",
    title: "Settings & Agents",
    links: [
      ["/settings", "Workspace & account"],
      ["/settings/sources", "Connections"],
      ["/settings/agents", "Agent keys"],
      ["/settings/runs", "Playbooks & runs"],
      ["/settings/imports", "Engine imports"],
      ["/settings/retention", "Retention & holds"],
    ],
  },
];

export function areaFor(path) {
  if (path === "/advanced" || path.startsWith("/advanced/")) return AREAS[3];
  return AREAS.find(
    (area) => path === area.path || path.startsWith(area.path + "/"),
  );
}
