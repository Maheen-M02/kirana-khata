import { BrandMark } from "@/components/brand";
import { LoginForm } from "@/components/login-form";

export const metadata = { title: "Login · Kirana Khata" };

export default function LoginPage() {
  return (
    <main className="flex min-h-dvh flex-col bg-ink">
      <section className="mx-auto w-full max-w-md px-6 pb-16 pt-12 text-white">
        <BrandMark className="h-14 w-14 ring-1 ring-white/15 rounded-2xl" />
        <h1 className="w-wide mt-6 text-[2.75rem] font-bold leading-[0.95] tracking-tight">
          Kirana Khata
        </h1>
        <p lang="hi" className="mt-2 text-2xl font-semibold text-marigold">किराना खाता</p>
        <p className="mt-5 max-w-[22ch] text-xl leading-snug text-white/85">
          Bolo, aur hisaab likh jayega. Udhaar, jama, bikri: sab awaaz se.
        </p>

        {/* What a turn looks like: the shopkeeper speaks, the khata answers and waits for "haan". */}
        <figure aria-label="Udaharan" className="mt-8 flex flex-col gap-2.5 text-lg">
          <p className="max-w-[85%] self-end rounded-2xl rounded-br-md bg-white/10 px-4 py-2.5">
            “Sharma ji ne ek sau bees udhaar liya”
          </p>
          <p className="max-w-[85%] rounded-2xl rounded-bl-md bg-marigold px-4 py-2.5 font-semibold text-ink">
            Ramesh Sharma, ek sau bees rupaye udhaar. Sahi hai?
          </p>
        </figure>
      </section>

      <section className="-mt-6 flex-1 rounded-t-[2rem] bg-paper">
        <div className="mx-auto w-full max-w-md px-6 pb-10 pt-8">
          <h2 className="text-2xl font-bold">Apni dukaan kholiye</h2>
          <p className="mt-1 text-base text-ink-soft">Mobile number aur 4 ank ka PIN daaliye.</p>
          <LoginForm />
        </div>
      </section>
    </main>
  );
}
