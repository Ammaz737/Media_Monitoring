"use client";

import { io, Socket } from "socket.io-client";
import { siteConfig } from "@/config/site";
import type { RealtimeUpdate } from "@/lib/types";

let socket: Socket | null = null;

function getSocketUrl(): string {
  const url = siteConfig.api.socketUrl?.trim();
  if (url) return url;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:5000`;
  }
  return "http://localhost:5000";
}

export function getSocket(): Socket {
  if (!socket) {
    socket = io(getSocketUrl(), {
      transports: ["websocket", "polling"],
      autoConnect: true,
    });
  }
  return socket;
}

export function subscribeRealtime(
  onUpdate: (data: RealtimeUpdate) => void,
  onConnected?: () => void,
  onDisconnected?: () => void
) {
  const s = getSocket();

  const handleConnect = () => {
    onConnected?.();
    s.emit("subscribe_updates", {});
  };

  const handleDisconnect = () => onDisconnected?.();

  s.on("connect", handleConnect);
  s.on("disconnect", handleDisconnect);
  s.on("connected", handleConnect);
  s.on("real_time_update", onUpdate);

  if (s.connected) handleConnect();

  return () => {
    s.off("connect", handleConnect);
    s.off("disconnect", handleDisconnect);
    s.off("connected", handleConnect);
    s.off("real_time_update", onUpdate);
  };
}
