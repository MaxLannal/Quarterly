import { Navigate, type RouteObject } from "react-router-dom";
import { AppShell } from "./AppShell";
import AboutPage from "./pages/AboutPage";
import AccountPage from "./pages/AccountPage";
import AdminModerationPage from "./pages/AdminModerationPage";
import AdminReviewPage from "./pages/AdminReviewPage";
import CommonsNewPage from "./pages/CommonsNewPage";
import CommonsPage from "./pages/CommonsPage";
import CommonsThreadPage from "./pages/CommonsThreadPage";
import ComparePlansPage from "./pages/ComparePlansPage";
import CourseInstructorPage from "./pages/CourseInstructorPage";
import CoursePage from "./pages/CoursePage";
import CoursesPage from "./pages/CoursesPage";
import DashboardPage from "./pages/DashboardPage";
import GuidelinesPage from "./pages/GuidelinesPage";
import HomePage from "./pages/HomePage";
import InstructorPage from "./pages/InstructorPage";
import InstructorsPage from "./pages/InstructorsPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import OnboardingPage from "./pages/OnboardingPage";
import PlanPage from "./pages/PlanPage";
import PlansPage from "./pages/PlansPage";
import PrivacyPage from "./pages/PrivacyPage";
import ProgramPage from "./pages/ProgramPage";
import ProgramsPage from "./pages/ProgramsPage";
import SignupPage from "./pages/SignupPage";
import ThreadPage from "./pages/ThreadPage";

/** One route per row of SPEC "Sitemap and every page". */
export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <HomePage /> },
      // The Ask page went with the homepage's question bar (issue #15): the planner is where a
      // student talks to the planner agent.
      { path: "/ask", element: <Navigate to="/plan" replace /> },
      { path: "/me", element: <DashboardPage /> },
      // The Feed moved into the Catalog page (issue #19).
      { path: "/feed", element: <Navigate to="/courses" replace /> },
      { path: "/forum", element: <CommonsPage /> },
      { path: "/forum/new", element: <CommonsNewPage /> },
      { path: "/forum/t/:id", element: <CommonsThreadPage /> },
      { path: "/onboarding", element: <OnboardingPage /> },
      { path: "/plan", element: <PlanPage /> },
      { path: "/plans", element: <PlansPage /> },
      { path: "/plans/compare", element: <ComparePlansPage /> },
      { path: "/courses", element: <CoursesPage /> },
      { path: "/courses/:code", element: <CoursePage /> },
      { path: "/courses/:code/i/:instructor", element: <CourseInstructorPage /> },
      { path: "/courses/:code/i/:instructor/t/:id", element: <ThreadPage /> },
      { path: "/instructors", element: <InstructorsPage /> },
      { path: "/instructors/:slug", element: <InstructorPage /> },
      { path: "/programs", element: <ProgramsPage /> },
      { path: "/programs/:id", element: <ProgramPage /> },
      { path: "/signup", element: <SignupPage /> },
      { path: "/login", element: <LoginPage /> },
      { path: "/account", element: <AccountPage /> },
      { path: "/guidelines", element: <GuidelinesPage /> },
      { path: "/privacy", element: <PrivacyPage /> },
      { path: "/about", element: <AboutPage /> },
      { path: "/admin/moderation", element: <AdminModerationPage /> },
      { path: "/admin", element: <AdminReviewPage /> },
      { path: "/admin/review", element: <AdminReviewPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
