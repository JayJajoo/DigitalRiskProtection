import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import Layout from '@/components/Layout'
import Part1Ingest from '@/pages/Part1Ingest'
import Part2Pipeline from '@/pages/Part2Pipeline'
import Metrics from '@/pages/Metrics'

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/part1" replace /> },
      { path: 'part1', element: <Part1Ingest /> },
      { path: 'part2', element: <Part2Pipeline /> },
      { path: 'metrics', element: <Metrics /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
