import { Link } from "react-router-dom";
import { inlineLinkClass, PageContainer, PageHeader } from "@/components/layout/page";
import { useQuestions } from "@/features/profile/questions";

/** SPEC "Accounts and anonymity": the "What is stored" table and the honest limits, verbatim in
 * substance. Change this page whenever that section changes. */
const STORED: { data: string; stored: string; linkable: string }[] = [
  {
    data: "Email address",
    stored: "Yes, in one place only: your account record.",
    linkable: "Yes, by anyone with access to the database.",
  },
  {
    data: "Username, password hash (argon2id), plans, your General Information and planner notes",
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
      "Not by the app. Rate limits use a scrambled counter that expires within 24 hours. No proxy or web server log keeps IP addresses.",
    linkable: "Weakly, for 24 hours.",
  },
  {
    data: "Timestamps",
    stored: "Day-level dates only (for example the day an account or post was created).",
    linkable: "Coarsely.",
  },
];

/** The planning step that uses each General Information answer (Issue #14 step 22), by field. */
const USED_FOR: Record<string, string> = {
  class_year: "Sets the years of your plan and your first quarter when you start as a first-year.",
  expected_graduation_term: "The last quarter of your plan.",
  intended_programs: "The requirements your plan is checked against.",
  entry_term: "The first quarter of your plan.",
  entry_year_level: "How many years your plan has left.",
  credits: "Requirements already met and units already earned, when your plan is checked.",
  taken_courses: "Placed on your plan as completed or in progress. The grade is optional; no GPA is computed from it.",
  post_grad_plan: "Read by the planner agent when it drafts or explains a plan.",
  pace: "Read by the planner agent: whether to aim for an early, on-time or flexible graduation.",
  wants_research: "Read by the planner agent when it suggests research courses.",
  research_areas: "Read by the planner agent when it suggests courses and research.",
  courses_per_term: "The course load the planner agent aims for each quarter.",
  terms_away: "Quarters the planner agent leaves free.",
  class_formats: "Read by the planner agent as a preference when it suggests courses.",
  theory_vs_application: "Read by the planner agent as a preference when it suggests courses.",
};

/** Each stored General Information field, read from the question file, and what plans with it. */
function GeneralInformation() {
  const questions = useQuestions();
  return (
    <>
      <h2 className="mt-6 font-display text-display-sm">Your General Information</h2>
      <p>
        When you are logged in, Quarterly keeps your answers to a short list of questions: the planner uses them for a first
        plan. You can see and change every answer, and export them as one Markdown file, on your{" "}
        <Link to="/me" className={inlineLinkClass}>
          dashboard
        </Link>
        . <strong>Quarterly stores no resume and no GPA.</strong> What you tell the planner chat is kept as working notes on
        your account (one set for all your plans), and is in the export too.
      </p>
      {questions.data ? (
        <div className="overflow-x-auto rounded-xl border border-hairline bg-surface-card">
          <table className="w-full border-collapse text-left text-body-sm">
            <caption className="sr-only">The General Information Quarterly stores, and the planning step that uses each answer</caption>
            <thead>
              <tr className="border-b border-hairline">
                <th scope="col" className="p-3 text-caption-uppercase uppercase text-muted">
                  Answer
                </th>
                <th scope="col" className="p-3 text-caption-uppercase uppercase text-muted">
                  Used for
                </th>
              </tr>
            </thead>
            <tbody>
              {questions.data.groups.flatMap((g) =>
                questions.data.questions
                  .filter((q) => q.group === g.id)
                  .map((q) => (
                    <tr key={q.id} className="border-b border-hairline align-top last:border-b-0">
                      <th scope="row" className="p-3 font-medium text-ink">
                        {q.label} <span className="block text-caption font-normal text-muted">{g.title}</span>
                      </th>
                      <td className="p-3">{USED_FOR[q.field] ?? "Read by the planner agent when it drafts or explains a plan."}</td>
                    </tr>
                  )),
              )}
            </tbody>
          </table>
        </div>
      ) : questions.error ? (
        <p className="text-body-sm text-muted">The list of questions could not be loaded. Your dashboard shows every answer.</p>
      ) : null}
      <p>Also kept with your account, and part of the account export:</p>
      <ul className="list-disc pl-6">
        <li>
          <strong>Your guide&apos;s memory:</strong> which questions it has asked and the last 24 messages of your conversation
          with it (emails and phone numbers removed), so it can pick up where you left off.
        </li>
        <li>
          <strong>What you follow:</strong> the courses and Commons questions you follow, and the feed categories you chose,
          for the feed and for alerts about new posts.
        </li>
        <li>
          <strong>What you have seen:</strong> the newest post the update alerts already showed you, so they show only new ones.
        </li>
        <li>
          <strong>Routes you kept</strong> from the dashboard&apos;s earlier versions.
        </li>
      </ul>
    </>
  );
}

export default function PrivacyPage() {
  return (
    <PageContainer width="reading" as="section" className="flex flex-col gap-6 text-body-md text-body [&_strong]:font-medium [&_strong]:text-ink">
      <PageHeader title="Privacy" description="What Quarterly stores about you, and why." className="mb-2" />
      <p>
        Quarterly is built by students, for students. This page says plainly what we keep about you
        and what that means. The short version:{" "}
        <strong>
          we store your @uchicago.edu email address and a hash of your password; other students only
          ever see a pseudonym that is different on every forum page.
        </strong>
      </p>

      <h2 className="mt-6 font-display text-display-sm">What is stored</h2>
      <div className="overflow-x-auto rounded-xl border border-hairline bg-surface-card">
        <table className="w-full border-collapse text-left text-body-sm">
          <caption className="sr-only">Data Quarterly stores and whether it can be linked to a person</caption>
          <thead>
            <tr className="border-b border-hairline">
              <th scope="col" className="p-3 text-caption-uppercase uppercase text-muted">
                Data
              </th>
              <th scope="col" className="p-3 text-caption-uppercase uppercase text-muted">
                Stored?
              </th>
              <th scope="col" className="p-3 text-caption-uppercase uppercase text-muted">
                Can it be linked to you?
              </th>
            </tr>
          </thead>
          <tbody>
            {STORED.map((row) => (
              <tr key={row.data} className="border-b border-hairline align-top last:border-b-0">
                <th scope="row" className="p-3 font-medium text-ink">
                  {row.data}
                </th>
                <td className="p-3">{row.stored}</td>
                <td className="p-3">{row.linkable}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <GeneralInformation />

      <h2 className="mt-6 font-display text-display-sm">How your email is used</h2>
      <ul className="list-disc space-y-2 pl-6 marker:text-gray-dark">
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

      <h2 className="mt-6 font-display text-display-sm">The honest limits</h2>
      <ul className="list-disc space-y-2 pl-6 marker:text-gray-dark">
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
        <li>
          If a moderator suspends an account, the day the suspension ends is stored on the account. Someone with a stolen copy of
          the database could count back from that day to a post removed when the suspension started and guess who wrote it. This
          only affects removed posts of suspended accounts.
        </li>
      </ul>

      <h2 className="mt-6 font-display text-display-sm">The AI features</h2>
      <p>
        When the AI features are on, what you type to the advisor and your plan are sent to an AI
        provider (Anthropic, with OpenRouter as a backup) to write the answer, after email
        addresses and phone numbers are removed. Forum posts are sent too, to write the “What
        students say” summaries and when the advisor looks them up. Your email address is never sent. Advisor chats are kept for 30
        days, and are deleted with their plan.
      </p>

      <h2 className="mt-6 font-display text-display-sm">Export and deletion</h2>
      <p>
        On your{" "}
        <Link to="/account" className={inlineLinkClass}>
          account page
        </Link>{" "}
        you can download your account details and plans as JSON, and delete your account. Deleting
        removes the account, its email address, your plans and your sessions. You choose whether your
        forum posts are deleted or kept as “[deleted account]”. Encrypted backups of the database
        are kept for 14 days, so a deleted account stays in them until they expire.
      </p>
    </PageContainer>
  );
}
