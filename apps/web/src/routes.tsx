import { Navigate, type RouteObject } from "react-router-dom";
import { AppShell } from "./AppShell";
import AboutPage from "./pages/AboutPage";
import AccountPage from "./pages/AccountPage";
import AdminModerationPage from "./pages/AdminModerationPage";
import AdminReviewPage from "./pages/AdminReviewPage";
import AskPage from "./pages/AskPage";
import CommonsNewPage from "./pages/CommonsNewPage";
import CommonsPage from "./pages/CommonsPage";
import CommonsThreadPage from "./pages/CommonsThreadPage";
import ComparePlansPage from "./pages/ComparePlansPage";
import CourseInstructorPage from "./pages/CourseInstructorPage";
import CoursePage from "./pages/CoursePage";
import CoursesPage from "./pages/CoursesPage";
import DashboardPage from "./pages/DashboardPage";
import FeedPage from "./pages/FeedPage";
import GuidelinesPage from "./pages/GuidelinesPage";
import HomePage from "./pages/HomePage";
import InstructorPage from "./pages/InstructorPage";
import InstructorsPage from "./pages/InstructorsPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
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
      // Campus companion (docs/BEST-OF-UCHICAGO-PLAN.md)
      { path: "/ask", element: <AskPage /> },
      { path: "/me", element: <DashboardPage /> },
      { path: "/feed", element: <FeedPage /> },
      { path: "/forum", element: <CommonsPage /> },
      { path: "/forum/new", element: <CommonsNewPage /> },
      { path: "/forum/t/:id", element: <CommonsThreadPage /> },
      // The planner setup moved into the registration form and the dashboard (Issue #16).
      { path: "/onboarding", element: <Navigate to="/me" replace /> },
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
