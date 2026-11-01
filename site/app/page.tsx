import { BookOpen, KeyRound, Languages, RotateCcw, ShieldCheck, Users } from "lucide-react";

import { BrandMark } from "@/components/brand";
import { VoiceDemo } from "@/components/voice-demo";

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
const LOGIN_URL = `${APP_URL.replace(/\/$/, "")}/login`;

// Every reply below is the app's real template output (backend/app/nlu/templates.py).
const SAYINGS = [
  {
    say: "Sharma ji ne ek sau bees udhaar liya",
    reply: "Ramesh Sharma, ek sau bees rupaye udhaar. Sahi hai?",
    kind: "Udhaar",
    tone: "text-udhaar",
  },
  {
    say: "Gupta ji ne teen sau jama kiye",
    reply: "Anil Gupta ne teen sau rupaye jama kiye. Sahi hai?",
    kind: "Jama",
    tone: "text-jama",
  },
  {
    say: "Pachaas rupaye nakad",
    reply: "Pachaas rupaye nakad bikri. Sahi hai?",
    kind: "Nakad bikri",
    tone: "text-ink",
  },
  {
    say: "Aaj kitni bikri hui?",
    reply: "Aaj ki bikri chaar sau sattar rupaye, 3 entry.",
    kind: "Batata hai",
    tone: "text-ink-soft",
  },
  {
    say: "Kis kis ka paisa baaki hai?",
    reply: "Sabse zyada baaki: Anil Gupta teen sau bees rupaye, Patil Kaka do sau rupaye.",
    kind: "Batata hai",
    tone: "text-ink-soft",
  },
  {
    say: "Pichhli entry cancel karo",
    reply: "Pichhli entry cancel karoon? Haan ya nahi?",
    kind: "Cancel",
    tone: "text-ink-soft",
  },
];

const TRUST = [
  {
    Icon: ShieldCheck,
    head: "Aapke “haan” ke bina kuch nahi likhta",
    body: "Har entry se pehle khata dohraata hai. “Nahi” boliye, to kuch nahi likhega.",
  },
  {
    Icon: RotateCcw,
    head: "Galti ho gayi? Cancel boliye",
    body: "Purani entry mitti nahi. Uske saamne cancel ki entry judti hai, taaki poora hisaab saaf dikhe.",
  },
  {
    Icon: Users,
    head: "Do Sharma ji? Khata poochta hai",
    body: "Ek jaise naam par wo poochta hai “Kaun se?” Aur ₹50,000 se badi rakam par do baar poochta hai.",
  },
  {
    Icon: Languages,
    head: "Hindi aur Hinglish dono",
    body: "Jaise aap grahak se baat karte hain, waise hi boliye. “Ek sau bees” ya “120”, dono chalega.",
  },
  {
    Icon: KeyRound,
    head: "Khata sirf aapka",
    body: "Aapke mobile number aur 4 ank ke PIN se khulta hai. Paanch baar galat PIN par 15 minute ke liye band.",
  },
  {
    Icon: BookOpen,
    head: "Paise paise ka hisaab",
    body: "Har grahak ka baaki, aaj ki bikri, aur kaun kitna jama kar gaya: sab ek jagah.",
  },
];

const FAQ = [
  {
    q: "Internet chahiye?",
    a: "Haan. Awaaz samajhne aur khata dekhne ke liye internet chahiye. Phone ka mobile data kaafi hai.",
  },
  {
    q: "Galat sun liya to?",
    a: "Likhne se pehle khata aapko sunaata hai ki usne kya samjha. Galat ho to “Nahi” boliye ya Nahi dabaiye. Kuch nahi likhega.",
  },
  {
    q: "Dukaan mein shor hai, chalega?",
    a: "Haan. Mic ke paas boliye aur jab tak bol rahe hain button dabaye rakhiye. Bolte waqt button ke chaaron taraf ka ghera badhta hai, usse pata chalta hai ki awaaz aa rahi hai.",
  },
  {
    q: "Kaun si bhasha?",
    a: "Hindi aur Hinglish. Naam Hindi mein ho ya English mein, dono chalega.",
  },
  {
    q: "Mera hisaab kaun dekh sakta hai?",
    a: "Sirf wo, jiske paas aapka mobile number aur PIN hai. Har dukaan ka khata alag rehta hai.",
  },
];

function OpenApp({ className = "" }: { className?: string }) {
  return (
    <a
      href={LOGIN_URL}
      className={`inline-flex h-14 items-center justify-center rounded-2xl bg-marigold px-7 text-xl font-bold text-ink shadow-[0_3px_0_hsl(var(--marigold-deep))] transition active:translate-y-[3px] active:shadow-none ${className}`}
    >
      Khata kholiye
    </a>
  );
}

export default function Home() {
  return (
    <>
      {/* Hero: the ink cover of the khata, with the real exchange beside the promise. */}
      <header className="bg-ink text-white">
        <nav className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <a href="#" className="flex items-center gap-2.5">
            <BrandMark className="h-10 w-10 rounded-xl ring-1 ring-white/15" />
            <span className="w-wide text-xl font-bold tracking-tight">Kirana Khata</span>
          </a>
          <a href={LOGIN_URL} className="rounded-full px-4 py-2 text-lg font-semibold text-marigold underline-offset-4 hover:underline">
            Login
          </a>
        </nav>

        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 pb-16 pt-8 sm:px-8 lg:grid-cols-[1.1fr_1fr] lg:gap-16 lg:pb-24 lg:pt-14">
          <div>
            <p lang="hi" className="text-2xl font-semibold text-marigold">किराना खाता</p>
            <h1 className="w-wide mt-3 text-balance text-[2.9rem] font-bold leading-[0.98] tracking-tight sm:text-6xl lg:text-[4rem] xl:text-[4.25rem]">
              Bolo, aur hisaab likh jayega.
            </h1>
            <p className="mt-6 max-w-[34ch] text-pretty text-xl leading-relaxed text-white/85 sm:text-2xl sm:leading-relaxed">
              Udhaar, jama aur aaj ki bikri: bas mic dabaiye aur boliye. Khata sunta hai, aapko dohraata hai, aur aapke
              “haan” ke baad hi likhta hai.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-4">
              <OpenApp />
              <a href="#kaise" className="text-lg font-semibold text-white/85 underline decoration-white/30 underline-offset-4">
                Kaise kaam karta hai
              </a>
            </div>
            <p className="mt-6 text-base text-white/60">Koi app download nahi. Phone ke Chrome mein khulta hai.</p>
          </div>
          <div className="flex justify-center lg:justify-end">
            <VoiceDemo />
          </div>
        </div>
      </header>

      <main>
        {/* What you can say: a page of the khata, sayings left of the red margin, effect right. */}
        <section aria-labelledby="bolo" className="mx-auto max-w-6xl px-5 py-16 sm:px-8 lg:py-24">
          <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
            <div>
              <h2 id="bolo" className="w-wide text-balance text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
                Jaise grahak se baat karte hain, waise boliye
              </h2>
              <p className="mt-5 max-w-[38ch] text-xl leading-relaxed text-ink-soft">
                Koi khaas shabd yaad nahi karne. Naam, rakam aur kaam bol dijiye; baaki khata samajh leta hai.
              </p>
            </div>
            <ul className="ledger-margin overflow-hidden rounded-[1.5rem] bg-white shadow-[0_0_0_1px_hsl(var(--rule))] [--col:8rem] sm:[--col:10rem]">
              {SAYINGS.map((s) => (
                <li key={s.say} className="flex items-stretch border-b border-rule last:border-b-0">
                  <div className="min-w-0 flex-1 py-4 pl-5 pr-4 sm:pl-6">
                    <p className="text-xl font-semibold leading-snug">“{s.say}”</p>
                    <p className="mt-1.5 text-base leading-snug text-ink-soft">{s.reply}</p>
                  </div>
                  <span className={`flex w-[8rem] shrink-0 items-center justify-end pr-5 text-right text-lg font-bold leading-tight sm:w-[10rem] sm:pr-6 ${s.tone}`}>
                    <span className="min-w-0">{s.kind}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* A real sequence, so it is numbered. */}
        <section id="kaise" aria-labelledby="kaise-h" className="bg-white py-16 shadow-[0_-1px_0_hsl(var(--rule)),0_1px_0_hsl(var(--rule))] lg:py-24">
          <div className="mx-auto max-w-6xl px-5 sm:px-8">
            <h2 id="kaise-h" className="w-wide text-4xl font-bold tracking-tight sm:text-5xl">Teen kadam</h2>
            <ol className="mt-10 grid gap-8 md:grid-cols-3 md:gap-10">
              {[
                ["Mic dabaake boliye", "Bada peela button dabaye rakhiye aur boliye. Chhodte hi khata sun leta hai."],
                ["Khata dohraata hai", "Wo bolkar aur likhkar batata hai ki usne kya samjha, aur poochta hai: “Sahi hai?”"],
                ["“Haan” boliye", "Haan bolte hi ya Haan dabaate hi entry khate mein likh jaati hai, grahak ke baaki ke saath."],
              ].map(([head, body], i) => (
                <li key={head} className="flex gap-5 md:flex-col md:gap-4">
                  <span className="num w-condensed flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-ink text-3xl font-bold text-marigold">
                    {i + 1}
                  </span>
                  <div>
                    <h3 className="text-2xl font-bold">{head}</h3>
                    <p className="mt-2 max-w-[34ch] text-lg leading-relaxed text-ink-soft">{body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section aria-labelledby="bharosa" className="mx-auto max-w-6xl px-5 py-16 sm:px-8 lg:py-24">
          <h2 id="bharosa" className="w-wide max-w-[18ch] text-balance text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
            Hisaab aapka, faisla bhi aapka
          </h2>
          <ul className="mt-12 grid gap-x-12 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
            {TRUST.map(({ Icon, head, body }) => (
              <li key={head} className="border-t-2 border-ink pt-5">
                <Icon className="h-7 w-7 text-marigold-deep" strokeWidth={2.25} aria-hidden />
                <h3 className="mt-3 text-2xl font-bold leading-snug">{head}</h3>
                <p className="mt-2 text-lg leading-relaxed text-ink-soft">{body}</p>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="phone" className="mx-auto max-w-6xl px-5 pb-16 sm:px-8 lg:pb-24">
          <div className="grid gap-10 rounded-[2rem] bg-marigold-wash px-6 py-10 sm:px-10 lg:grid-cols-[1fr_1.2fr] lg:items-center lg:gap-16 lg:px-14 lg:py-14">
            <div>
              <h2 id="phone" className="w-wide text-balance text-4xl font-bold leading-tight tracking-tight">
                Phone par app ki tarah lagaiye
              </h2>
              <p className="mt-4 max-w-[36ch] text-xl leading-relaxed text-ink-soft">
                Play Store ki zaroorat nahi. Ek baar lagaiye, phir icon dabaate hi khata khulega.
              </p>
            </div>
            <ol className="flex flex-col gap-4">
              {[
                ["Chrome mein Kirana Khata kholiye", "Neeche “Khata kholiye” dabaiye."],
                ["Upar ⋮ menu dabaiye", "Phir “Add to Home screen” ya “App install karein” chuniye."],
                ["Home screen par icon aa jayega", "Peela mic wala icon. Mobile number aur PIN se login kijiye."],
              ].map(([head, body], i) => (
                <li key={head} className="flex gap-4 rounded-2xl bg-white px-5 py-4">
                  <span className="num w-condensed text-3xl font-bold leading-none text-marigold-deep">{i + 1}</span>
                  <div>
                    <p className="text-xl font-semibold leading-snug">{head}</p>
                    <p className="mt-1 text-base leading-snug text-ink-soft">{body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section aria-labelledby="sawaal" className="mx-auto max-w-3xl px-5 pb-20 sm:px-8 lg:pb-28">
          <h2 id="sawaal" className="w-wide text-4xl font-bold tracking-tight">Aapke sawaal</h2>
          <div className="mt-8 border-t border-rule">
            {FAQ.map(({ q, a }) => (
              <details key={q} className="group border-b border-rule">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-5 text-xl font-semibold [&::-webkit-details-marker]:hidden">
                  {q}
                  <span aria-hidden className="text-3xl font-normal leading-none text-ink-soft transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="max-w-[60ch] pb-6 text-lg leading-relaxed text-ink-soft">{a}</p>
              </details>
            ))}
          </div>
        </section>
      </main>

      <footer className="bg-ink text-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-8 px-5 py-14 sm:px-8 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="w-wide text-balance text-4xl font-bold leading-tight tracking-tight sm:text-5xl">Aaj ka hisaab, aaj hi.</p>
            <p className="mt-3 text-lg text-white/70">Mic dabaiye, boliye, “haan” kahiye. Bas.</p>
          </div>
          <OpenApp className="self-start lg:self-auto" />
        </div>
        <div className="mx-auto max-w-6xl border-t border-white/10 px-5 py-6 text-base text-white/55 sm:px-8">
          Kirana Khata. Awaaz samajhne aur bolne ki technology: Gnani.ai
        </div>
      </footer>
    </>
  );
}
