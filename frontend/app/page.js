"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"

export default function LoginPage() {
  const [bookingId, setBookingId] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  async function handleSearch(e) {
    e.preventDefault()
    setError("")

    if (!bookingId.trim()) {
      setError("Please enter a booking ID.")
      return
    }

    setLoading(true)
    router.push(`/booking/${bookingId.trim().toUpperCase()}`)
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 to-blue-900 flex items-center justify-center p-4">

      {/* Hero section */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="w-full max-w-md"
      >

        {/* Logo / branding */}
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">✈️</div>
          <h1 className="text-3xl font-bold text-white">AI Flight Assistant</h1>
          <p className="text-blue-300 mt-2">View your booking details below</p>
        </div>

        {/* Login card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6">
            Enter Your Booking ID
          </h2>

          <form onSubmit={handleSearch} className="space-y-4">
            <input
              type="text"
              placeholder="e.g. BK-20260909-XYZ123"
              value={bookingId}
              onChange={(e) => setBookingId(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-4 py-3 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 uppercase placeholder:normal-case"
            />

            {error && (
              <p className="text-red-500 text-sm">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition-colors duration-200 disabled:opacity-50"
            >
              {loading ? "Searching..." : "View Booking →"}
            </button>
          </form>

          <p className="text-center text-gray-400 text-sm mt-6">
            Your booking ID was shared via SMS and email after your call.
          </p>
        </div>

        {/* Demo note */}
        <p className="text-center text-blue-300 text-xs mt-4">
          ⚠️ This is a demo project. No real payments are processed.
        </p>

      </motion.div>
    </main>
  )
}