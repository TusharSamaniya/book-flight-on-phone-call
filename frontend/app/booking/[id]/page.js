"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { supabase } from "../../../lib/supabase"

// Small reusable card component
function InfoCard({ title, children, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className="bg-white rounded-2xl shadow-md p-6"
    >
      <h3 className="text-lg font-semibold text-gray-700 mb-4 border-b pb-2">
        {title}
      </h3>
      {children}
    </motion.div>
  )
}

// Small reusable row inside a card
function InfoRow({ label, value }) {
  return (
    <div className="flex justify-between py-2 border-b border-gray-100 last:border-0">
      <span className="text-gray-500 text-sm">{label}</span>
      <span className="text-gray-800 text-sm font-medium text-right max-w-xs">
        {value || "—"}
      </span>
    </div>
  )
}

export default function BookingPage() {
  const { id } = useParams()
  const router = useRouter()

  const [booking, setBooking] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    async function fetchBooking() {
      if (!id) return

      const { data, error } = await supabase
        .from("bookings")
        .select("*")
        .eq("booking_id", id)
        .single()

      if (error || !data) {
        setError("No booking found with that ID. Please check and try again.")
      } else {
        setBooking(data)
      }

      setLoading(false)
    }

    fetchBooking()
  }, [id])

  // Loading state
  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 to-blue-900 flex items-center justify-center">
        <div className="text-center">
          <div className="text-5xl mb-4 animate-bounce">✈️</div>
          <p className="text-white text-xl">Loading your booking...</p>
        </div>
      </main>
    )
  }

  // Error state
  if (error) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 to-blue-900 flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-white rounded-2xl p-8 max-w-md text-center"
        >
          <div className="text-5xl mb-4">❌</div>
          <h2 className="text-xl font-bold text-gray-800 mb-2">Booking Not Found</h2>
          <p className="text-gray-500 mb-6">{error}</p>
          <button
            onClick={() => router.push("/")}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Try Again
          </button>
        </motion.div>
      </main>
    )
  }

  // Parse trip_details JSON (stored as JSONB in Supabase)
  const trip = booking.trip_details || {}

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 to-blue-900 p-4 md:p-8">

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-3xl mx-auto mb-8"
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-white">
              ✈️ AI Flight Assistant
            </h1>
            <p className="text-blue-300 mt-1">Booking Dashboard</p>
          </div>
          <button
            onClick={() => router.push("/")}
            className="text-blue-300 hover:text-white text-sm underline"
          >
            ← Search another
          </button>
        </div>
      </motion.div>

      {/* Main content */}
      <div className="max-w-3xl mx-auto space-y-4">

        {/* Booking status banner */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4 }}
          className="bg-green-500 rounded-2xl p-4 flex items-center gap-4"
        >
          <div className="text-3xl">✅</div>
          <div>
            <p className="text-white font-bold text-lg">Booking Confirmed</p>
            <p className="text-green-100 text-sm">
              Booking ID: <strong>{booking.booking_id}</strong>
            </p>
          </div>
          <div className="ml-auto text-right">
            <p className="text-green-100 text-sm">Status</p>
            <p className="text-white font-semibold capitalize">{booking.status}</p>
          </div>
        </motion.div>

        {/* Flight Details */}
        <InfoCard title="✈️ Flight Details" delay={0.1}>
          <InfoRow label="From" value={trip.origin} />
          <InfoRow label="To" value={trip.destination} />
          <InfoRow label="Travel Date" value={trip.travel_date} />
          <InfoRow label="Departure Time" value={trip.departure_time} />
          <InfoRow label="Cabin Class" value={trip.cabin_class} />
          <InfoRow label="Passengers" value={trip.passengers} />
          <InfoRow label="Preferred Airline" value={trip.airline_preference} />
        </InfoCard>

        {/* Passenger Info */}
        <InfoCard title="👤 Passenger Information" delay={0.2}>
          <InfoRow label="Full Name" value={booking.passenger_name} />
          <InfoRow label="Phone" value={booking.passenger_phone} />
          <InfoRow label="Email" value={booking.passenger_email} />
        </InfoCard>

        {/* Payment Info */}
        <InfoCard title="💳 Payment Details" delay={0.3}>
          <InfoRow
            label="Amount"
            value={`${booking.currency} ${(booking.price / 100).toFixed(2)}`}
          />
          <InfoRow label="Status" value="✅ Demo Payment Successful" />
          <div className="mt-3 bg-yellow-50 border border-yellow-200 rounded-lg p-3">
            <p className="text-yellow-700 text-xs">
              ⚠️ This is a demo booking. No real payment was processed.
            </p>
          </div>
        </InfoCard>

        {/* Booked At */}
        <InfoCard title="📅 Booking Info" delay={0.4}>
          <InfoRow
            label="Booked On"
            value={new Date(booking.created_at).toLocaleString()}
          />
          <InfoRow label="Booking ID" value={booking.booking_id} />
        </InfoCard>

        {/* Footer */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="text-center text-blue-300 text-sm pb-8"
        >
          Thank you for using AI Flight Assistant ✈️
        </motion.p>

      </div>
    </main>
  )
}