import { Link } from "react-router-dom";
import { linkClass } from "@/features/auth/ui";

/** SPEC "Accounts and anonymity": the "What is stored" table and the honest limits, verbatim in
 * substance. Change this page whenever that section changes. */
const STORED: { data: string; stored: string; linkable: string }[] = [
  {
    data: "Email address",
    stored: "Yes, in one place only: your account record.",
    linkable: "Yes, by anyone with access to the database.",
  },
  {
    data: "Username, password hash (argon2id), plans",
    stored: "Yes. We never store the password itself.",
    linkable: "Yes, through the email address on the same account.",
  },
  {
    data: "Forum posts, comments, votes",
    stored: "Yes, under a per-page author code computed from a server key, your account and the page.",
    linkable:
      "Not from a leaked database alone. Yes for someone who holds both the server key and the database.",
  },
  {
    data: "IP addresses",
    stored:
      "Not by the app. Rate limits use a scrambled counter that expires within 24 hours. Proxy logs are cut to the first three numbers of the address and kept 24 hours for abuse response.",
    linkable: "Weakly, for 24 hours.",
  },
  {
    data: "Timestamps",
    stored: "Day-level dates only (for example the day an account or post was created).",
    linkable: "Coarsely.",
  },
];

export default function PrivacyPage() {
  return (
    <section className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold">Privacy</h1>
      <p>
        Quarterly is built by students, for students. This page says plainly what we keep about you
        and what that means. The short version:{" "}
        <strong>
          we store your @uchicago.edu email address and a hash of your password; other students only
          ever see a pseudonym that is different on every forum page.
        </strong>
      </p>

      <h2 className="text-lg font-semibold">What is stored</h2>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <caption className="sr-only">Data Quarterly stores and whether it can be linked to a person</caption>
          <thead>
            <tr className="border-b border-border">
              <th scope="col" className="p-2">
                Data
              </th>
              <th scope="col" className="p-2">
                Stored?
              </th>
              <th scope="col" className="p-2">
                Can it be linked to you?
              </th>
            </tr>
          </thead>
          <tbody>
            {STORED.map((row) => (
              <tr key={row.data} className="border-b border-border align-top">
                <th scope="row" className="p-2 font-medium">
                  {row.data}
                </th>
                <td className="p-2">{row.stored}</td>
                <td className="p-2">{row.linkable}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="text-lg font-semibold">How your email is used</h2>
      <ul className="list-disc space-y-2 pl-6">
        <li>
          To check once that you are a UChicago student (a 6-digit code, kept for 10 minutes), and to
          let you reset a lost password.
        </li>
        <li>
          It is never shown to other users, never written to logs, and never copied into forum, plan
          or analytics records.
        </li>
        <li>One account per email address.</li>
        <li>
          Our email provider learns that Quarterly emailed your address. The message contains only
          the code.
        </li>
      </ul>

      <h2 className="text-lg font-semibold">The honest limits</h2>
      <ul className="list-disc space-y-2 pl-6">
        <li>
          <strong>The forum is pseudonymous, not anonymous to the people who run Quarterly.</strong>{" "}
          A builder or administrator who has both the database and the server key can link a post to
          an account, and so to an email address. We do not do this in normal operation, but you
          should know it is possible.
        </li>
        <li>
          <strong>If the database leaked</strong>, it would reveal which email addresses have
          accounts and their plans. Posts on different pages still could not be joined to one account
          without the server key.
        </li>
        <li>
          What you write can identify you. A pseudonym does not help if a review says which section
          you sat in and what you said in class.
        </li>
        <li>Each forum page gives you a different pseudonym, so readers cannot follow you across pages.</li>
      </ul>

      <h2 className="text-lg font-semibold">Export and deletion</h2>
      <p>
        On your{" "}
        <Link to="/account" className={linkClass}>
          account page
        </Link>{" "}
        you can download your account details and plans as JSON, and delete your account. Deleting
        removes the account, its email address, your plans and your sessions. You choose whether your
        forum posts are deleted or kept as “[deleted account]”.
      </p>
    </section>
  );
}
