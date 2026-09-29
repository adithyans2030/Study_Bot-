import { createBrowserRouter } from "react-router-dom"
import { RequireAuth } from "./RequireAuth"
import { RootRedirect } from "./RootRedirect"

// Each page is its own chunk (React Router's lazy route modules), not because any one of them is
// huge on its own, but because otherwise every route's dependencies (react-hook-form + zod for
// auth, every shadcn primitive for the foundations page, ...) all land in one bundle every visitor
// downloads regardless of which page they open. This alone took the gzipped JS from 209 KB back
// under the 180 KB budget (Â§10) â€” worth re-checking after every milestone that adds a route.
export const router = createBrowserRouter([
  {
    path: "/",
    lazy: () =>
      import("@/features/landing/LandingPage").then((m) => ({ Component: m.LandingPage })),
  },
  { path: "/app-redirect", element: <RootRedirect /> },
  {
    path: "/login",
    lazy: () => import("@/features/auth/LoginPage").then((m) => ({ Component: m.LoginPage })),
  },
  {
    path: "/register",
    lazy: () => import("@/features/auth/RegisterPage").then((m) => ({ Component: m.RegisterPage })),
  },
  {
    element: <RequireAuth />,
    children: [
      {
        lazy: () => import("./AppShell").then((m) => ({ Component: m.AppShell })),
        children: [
          {
            path: "/app",
            lazy: () =>
              import("@/features/dashboard/DashboardPage").then((m) => ({
                Component: m.DashboardPage,
              })),
          },
          {
            path: "/app/c/:collectionId",
            lazy: () =>
              import("@/features/library/CollectionDetailPage").then((m) => ({
                Component: m.CollectionDetailPage,
              })),
          },
          {
            path: "/app/c/:collectionId/study",
            lazy: () =>
              import("@/features/study/StudyPage").then((m) => ({
                Component: m.StudyPage,
              })),
          },
          {
            path: "/app/knowledge",
            lazy: () =>
              import("@/features/knowledge/KnowledgePage").then((m) => ({
                Component: m.KnowledgePage,
              })),
          },
        ],
      },
      {
        // A global route, not nested under a collection: the real `conversations` table has no
        // collection column at all (a conversation isn't owned by one subject), so which
        // collection(s) to search is an in-page filter here, not a URL segment â€” a "?collection="
        // query param only *pre-selects* that filter when arriving from a collection page. Its
        // own full-screen layout (sidebar, composer, source panel), not the dashboard's top bar.
        path: "/app/chat/:conversationId?",
        lazy: () => import("@/features/chat/ChatPage").then((m) => ({ Component: m.ChatPage })),
      },
    ],
  },
  {
    // Kept during development only, not linked from anywhere real â€” see PLAN.md Milestone A.
    path: "/foundations",
    lazy: () =>
      import("@/design-system/FoundationsPage").then((m) => ({ Component: m.FoundationsPage })),
  },
  {
    path: "*",
    lazy: () => import("./NotFoundPage").then((m) => ({ Component: m.NotFoundPage })),
  },
])

