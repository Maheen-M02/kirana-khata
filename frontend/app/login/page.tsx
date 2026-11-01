import { LoginForm } from "@/components/login-form";

export const metadata = { title: "Login · Kirana Khata" };

export default function LoginPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-6 px-4 py-10">
      <header className="text-center">
        <h1 className="text-3xl font-bold">Kirana Khata</h1>
        <p className="mt-2 text-lg text-muted-foreground">Bolo, aur hisaab likh jayega.</p>
      </header>
      <LoginForm />
    </main>
  );
}
