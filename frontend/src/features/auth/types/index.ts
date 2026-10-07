export interface User {
  id: number;
  email: string;
  name: string;
  picture_url: string;
  role: "user" | "admin";
}

export interface Me {
  user: User | null;
  google_enabled: boolean;
  dev_login: boolean;
  lyrics_sources: string[];
}

export interface PairStart {
  code: string;
  poll_secret: string;
  approve_url: string;
  qr_svg: string;
  expires_in: number;
}
