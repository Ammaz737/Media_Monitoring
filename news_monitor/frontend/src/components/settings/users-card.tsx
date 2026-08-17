"use client";

import { FormEvent, useEffect, useState } from "react";
import { Users } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/components/auth/auth-provider";
import type { AuthUser } from "@/lib/types";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

const ROLES = ["admin", "operator", "viewer"] as const;

export function UsersCard() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<string>("viewer");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const res = await api.listUsers();
    setUsers(res.users);
  };

  useEffect(() => {
    load().catch((e) =>
      setError(e instanceof Error ? e.message : "Failed to load users")
    );
  }, []);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.createUser({ username: username.trim(), password, role });
      setUsername("");
      setPassword("");
      setRole("viewer");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  };

  const onRole = async (id: number, nextRole: string) => {
    setError(null);
    try {
      await api.updateUser(id, { role: nextRole });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  };

  const onDelete = async (id: number) => {
    setError(null);
    try {
      await api.deleteUser(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <SectionCard
      title="Users & roles"
      icon={<Users className="h-5 w-5 text-primary" />}
      accent="primary"
    >
      <div className="space-y-4" dir="ltr">
        {error && (
          <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </p>
        )}
        

        <form onSubmit={onCreate} className="grid gap-3 sm:grid-cols-4">
          <div className="sm:col-span-1">
            <Label htmlFor="new-user">Username</Label>
            <Input
              id="new-user"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              minLength={2}
              required
            />
          </div>
          <div className="sm:col-span-1">
            <Label htmlFor="new-pass">Password</Label>
            <Input
              id="new-pass"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={6}
              required
            />
          </div>
          <div className="sm:col-span-1">
            <Label htmlFor="new-role">Role</Label>
            <select
              id="new-role"
              className="mt-0 flex h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <Button type="submit" className="w-full" disabled={busy}>
              Add user
            </Button>
          </div>
        </form>
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-100">
          {users.map((u) => (
            <li
              key={u.id}
              className="flex flex-wrap items-center justify-between gap-3 px-3 py-2.5"
            >
              <div className="flex items-center gap-2">
                <span className="font-medium text-slate-800">{u.username}</span>
                <Badge variant="secondary">{u.role}</Badge>
                {!u.is_active && <Badge variant="danger">disabled</Badge>}
              </div>
              <div className="flex items-center gap-2">
                <select
                  className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs"
                  value={u.role}
                  onChange={(e) => onRole(u.id, e.target.value)}
                  disabled={u.id === me.id}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={u.id === me.id}
                  onClick={() => onDelete(u.id)}
                >
                  Delete
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </SectionCard>
  );
}
