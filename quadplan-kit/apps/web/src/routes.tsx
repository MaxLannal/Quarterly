import type { RouteObject } from "react-router-dom";
import { AppShell } from "./AppShell";
import AboutPage from "./pages/AboutPage";
import AccountPage from "./pages/AccountPage";
import AdminPage from "./pages/AdminPage";
import ComparePlansPage from "./pages/ComparePlansPage";
import CourseInstructorPage from "./pages/CourseInstructorPage";
import CoursePage from "./pages/CoursePage";
import CoursesPage from "./pages/CoursesPage";
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
      { path: "/admin/*", element: <AdminPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
