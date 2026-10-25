import React from "react";
import { beforeEach, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import WorkspaceHome from "./WorkspaceHome";
import { api } from "../services/api";
import { useSession } from "../session";

vi.mock("../services/api", () => ({api:vi.fn()}));
vi.mock("../session", () => ({useSession:vi.fn()}));
beforeEach(() => {
  useSession.mockReturnValue({user:{name:"Owner",workspace:"Bluewater Team",role:"admin"}});
  api.mockImplementation(async path => path === "/team" ? [{id:"p1",name:"Fictional Reviewer",email:"review@example.invalid",role:"reviewer"}] : []);
});
test("named workspace groups records and their upload, invite and review actions", async () => {
  render(<MemoryRouter><WorkspaceHome/></MemoryRouter>);
  await screen.findByText("Fictional Reviewer");
  expect(screen.getByRole("heading",{name:"Bluewater Team"})).toBeTruthy();
  expect(screen.getByRole("heading",{name:"Company policies"})).toBeTruthy();
  expect(screen.getByRole("link",{name:"Add policy"}).getAttribute("href")).toBe("/policies/library/new");
  expect(screen.getByRole("link",{name:"Add activity"}).getAttribute("href")).toBe("/inbox/transactions?mode=csv");
  expect(screen.getByRole("link",{name:"Invite people"}).getAttribute("href")).toBe("/settings?section=Team");
  expect(screen.getByRole("navigation",{name:"Workspace sections"})).toBeTruthy();
});
test("auditors see the workspace inventory without create or invitation actions", async () => {
  useSession.mockReturnValue({user:{workspace:"Bluewater Team",role:"auditor"}});
  render(<MemoryRouter><WorkspaceHome/></MemoryRouter>);
  await screen.findByText("Fictional Reviewer");
  expect(screen.queryByRole("link",{name:"Add policy"})).toBeNull();
  expect(screen.queryByRole("link",{name:"Invite people"})).toBeNull();
});
