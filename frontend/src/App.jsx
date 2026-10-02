import { useEffect, useState } from "react";

import {
  TrainFront,
  MapPin,
  Clock3,
  ShieldCheck,
  Users,
  Ticket,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Zap,
  Database,
  LockKeyhole,
  Activity,
} from "lucide-react";

import "./App.css";

const API = "https://tatkal-rush-api.onrender.com";

function App() {
  // ============================================================
  // DASHBOARD STATE
  // ============================================================

  const [seats, setSeats] = useState([]);
  const [stats, setStats] = useState(null);
  const [queue, setQueue] = useState([]);

  // ============================================================
  // BOOKING STATE
  // ============================================================

  const [userId, setUserId] = useState("");
  const [reservation, setReservation] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(0);

  const [loading, setLoading] = useState(false);

  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");

  // ============================================================
  // SIMULATION STATE
  // ============================================================

  const [simulationLoading, setSimulationLoading] =
    useState(false);

  const [simulationResult, setSimulationResult] =
    useState(null);

  // ============================================================
  // LOAD DASHBOARD
  // ============================================================

  const loadDashboard = async () => {
    try {
      const [
        seatResponse,
        statsResponse,
        queueResponse,
      ] = await Promise.all([
        fetch(`${API}/seats`),
        fetch(`${API}/stats`),
        fetch(`${API}/queue`),
      ]);

      const seatData = await seatResponse.json();
      const statsData = await statsResponse.json();
      const queueData = await queueResponse.json();

      setSeats(seatData.seats || []);
      setStats(statsData);
      setQueue(queueData.queue || []);
    } catch (error) {
      console.error(error);

      setMessage(
        "Unable to connect to Tatkal Rush backend."
      );

      setMessageType("error");
    }
  };

  // ============================================================
  // INITIAL LOAD + LIVE REFRESH
  // ============================================================

  useEffect(() => {
    loadDashboard();

    const interval = setInterval(() => {
      loadDashboard();
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  // ============================================================
  // RESERVATION COUNTDOWN
  // ============================================================

  useEffect(() => {
    if (!reservation || secondsLeft <= 0) {
      return;
    }

    const timer = setInterval(() => {
      setSecondsLeft((current) => {
      if (current <= 1) {
  clearInterval(timer);

  setReservation((currentReservation) => ({
    ...currentReservation,
    status: "EXPIRED",
  }));

  setMessage(
    "Payment window expired. The temporary seat hold has been released and the seat is available for another passenger."
  );

  setMessageType("error");

  setTimeout(() => {
    loadDashboard();
  }, 1200);

  return 0;
}

        return current - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [reservation, secondsLeft]);

  // ============================================================
  // BOOK SEAT
  // ============================================================

  const bookSeat = async () => {
    const cleanUserId = userId.trim();

    if (!cleanUserId) {
      setMessage(
        "Enter a passenger / user ID first."
      );

      setMessageType("error");

      return;
    }

    setLoading(true);
    setMessage("");

    try {
      const response = await fetch(`${API}/book`, {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          user_id: cleanUserId,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setReservation(data);

        setSecondsLeft(
          data.expires_in_seconds || 30
        );

        setMessage(
  `Seat ${data.seat} successfully HELD. Your booking request acquired the available seat first. The seat is temporarily locked for you while payment is pending. Complete payment before the 30-second timer expires.`
);

        setMessageType("success");
      } else {
  const reason =
    data.status === "SOLD_OUT" ||
    data.message?.toLowerCase().includes("sold")
      ? "Booking not allocated. The available seat was already acquired and HELD by another concurrent request. No other seat is currently available. Your request was safely rejected to prevent double booking."
      : data.message || "Tatkal seats are currently unavailable.";

  setMessage(reason);
  setMessageType("error");
}

      await loadDashboard();
    } catch (error) {
      console.error(error);

      setMessage(
        "Booking request failed. Check the backend server."
      );

      setMessageType("error");
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // PAYMENT SUCCESS
  // ============================================================

  const paymentSuccess = async () => {
    if (!reservation) {
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(
        `${API}/payment/${reservation.reservation_id}/success`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (data.success) {
        setMessage(
          `Booking confirmed! ${data.seat} is now BOOKED.`
        );

        setMessageType("success");

        setReservation({
          ...reservation,
          status: "BOOKED",
        });

        setSecondsLeft(0);
      } else {
        setMessage(
          data.message ||
            "Payment could not be completed."
        );

        setMessageType("error");

        setReservation(null);
        setSecondsLeft(0);
      }

      await loadDashboard();
    } catch (error) {
      console.error(error);

      setMessage("Payment request failed.");
      setMessageType("error");
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // PAYMENT FAILURE
  // ============================================================

  const paymentFailure = async () => {
    if (!reservation) {
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(
        `${API}/payment/${reservation.reservation_id}/failure`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (data.success) {
        setMessage(
          `${data.seat} released back to Tatkal inventory.`
        );

        setMessageType("error");
      } else {
        setMessage(
          data.message ||
            "Unable to release reservation."
        );

        setMessageType("error");
      }

      setReservation(null);
      setSecondsLeft(0);

      await loadDashboard();
    } catch (error) {
      console.error(error);

      setMessage(
        "Payment failure request failed."
      );

      setMessageType("error");
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // LIVE CONCURRENCY SIMULATION
  // ============================================================

  const runRushSimulation = async () => {
    setSimulationLoading(true);
    setSimulationResult(null);

    setMessage("");
    setMessageType("");

    try {
      const response = await fetch(
        `${API}/simulate-rush`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message ||
            "Rush simulation failed."
        );
      }

      setSimulationResult(data);

      setMessage(
        `1,000-user rush completed in ${data.results.execution_time_seconds}s — Consistency ${data.verification.consistency}.`
      );

      setMessageType(
        data.verification.consistency === "PASS"
          ? "success"
          : "error"
      );
    } catch (error) {
      console.error(error);

      setMessage(
        "Unable to run rush simulation. Check the FastAPI server."
      );

      setMessageType("error");
    } finally {
      setSimulationLoading(false);
    }
  };

  // ============================================================
  // RESET BOOKING
  // ============================================================

  const resetBooking = () => {
    setReservation(null);
    setSecondsLeft(0);
    setUserId("");
    setMessage("");
  };

  // ============================================================
  // DISPLAY VALUES
  // ============================================================

  const seatStats = stats?.seats || {};
  const queueStats = stats?.queue || {};

  const recentQueue = [...queue]
    .reverse()
    .slice(0, 8);

  const simulationStats =
    simulationResult?.results;

  const simulationConfig =
    simulationResult?.configuration;

  const simulationVerification =
    simulationResult?.verification;

  // ============================================================
  // UI
  // ============================================================

  return (
    <div className="app">
      {/* ======================================================
          TOP BAR
      ====================================================== */}

      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">
            <TrainFront size={28} />
          </div>

          <div>
            <h1>Tatkal Rush</h1>

            <p>
              High-Concurrency Railway Booking
            </p>
          </div>
        </div>

        <div className="system-online">
          <span className="online-dot"></span>

          SYSTEM ONLINE
        </div>
      </header>

      {/* ======================================================
          HERO
      ====================================================== */}

      <section className="hero">
        <div className="hero-overlay"></div>

        <div className="hero-content">
          <div className="hero-badge">
            <Zap size={16} />

            TATKAL QUOTA LIVE
          </div>

          <h2>
            One Train.
            <span> Thousands of Users.</span>
          </h2>

          <p>
            A concurrency-safe railway booking
            prototype engineered to prevent double
            booking under extreme Tatkal traffic.
          </p>

          <div className="route-card">
            <div className="station">
              <span className="station-code">
                MAS
              </span>

              <strong>
                Chennai Central
              </strong>

              <small>
                <MapPin size={13} />
                Chennai
              </small>
            </div>

            <div className="route-line">
              <div className="route-dot"></div>

              <div className="rail-line"></div>

              <div className="train-circle">
                <TrainFront size={20} />
              </div>

              <div className="rail-line"></div>

              <div className="route-dot"></div>
            </div>

            <div className="station station-right">
              <span className="station-code">
                NDLS
              </span>

              <strong>
                New Delhi
              </strong>

              <small>
                <MapPin size={13} />
                Delhi
              </small>
            </div>
          </div>

          <div className="journey-info">
            <div>
              <Clock3 size={17} />
              <span>
                Tatkal Booking Window
              </span>
            </div>

            <div>
              <ShieldCheck size={17} />
              <span>
                Concurrency Protected
              </span>
            </div>

            <div>
              <LockKeyhole size={17} />
              <span>
                PostgreSQL Row Locking
              </span>
            </div>
          </div>
        </div>
      </section>

      <main className="dashboard">
        {/* ====================================================
            STATS
        ==================================================== */}

        <section className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon available-icon">
              <Ticket size={22} />
            </div>

            <div>
              <span>
                Available Seats
              </span>

              <strong>
                {seatStats.available ?? 0}
              </strong>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon held-icon">
              <Clock3 size={22} />
            </div>

            <div>
              <span>
                Active Holds
              </span>

              <strong>
                {seatStats.held ?? 0}
              </strong>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon booked-icon">
              <CheckCircle2 size={22} />
            </div>

            <div>
              <span>
                Confirmed
              </span>

              <strong>
                {seatStats.booked ?? 0}
              </strong>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon queue-icon">
              <Users size={22} />
            </div>

            <div>
              <span>
                Queue Requests
              </span>

              <strong>
                {queueStats.total_requests ?? 0}
              </strong>
            </div>
          </div>
        </section>

        {/* ====================================================
            SEAT INVENTORY
        ==================================================== */}

        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">
                LIVE INVENTORY
              </span>

              <h3>
                Tatkal Seat Availability
              </h3>

              <p>
                Seat status refreshes
                automatically from PostgreSQL
                every two seconds.
              </p>
            </div>

            <button
              className="refresh-button"
              onClick={loadDashboard}
            >
              <RefreshCw size={17} />

              Refresh
            </button>
          </div>

          <div className="seat-legend">
            <span>
              <i className="legend-dot available"></i>
              Available
            </span>

            <span>
              <i className="legend-dot held"></i>
              Held
            </span>

            <span>
              <i className="legend-dot booked"></i>
              Booked
            </span>
          </div>

          <div className="seat-grid">
            {seats.map((seat) => (
              <div
                key={seat.id}
                className={`seat-card ${seat.status.toLowerCase()}`}
              >
                <div className="seat-top">
                  <Ticket size={18} />

                  <span>
                    {seat.status}
                  </span>
                </div>

                <strong>
                  {seat.seat_number}
                </strong>
<small>
  {seat.status === "HELD" &&
  reservation?.status === "HELD" &&
  reservation?.seat === seat.seat_number
    ? `Payment hold • 00:${String(secondsLeft).padStart(2, "0")}`
    : "Tatkal Seat"}
</small>
              </div>
            ))}
          </div>
        </section>

        {/* ====================================================
            BOOKING + RESERVATION
        ==================================================== */}

        <section className="two-column">
          <div className="panel booking-panel">
            <span className="eyebrow">
              TATKAL BOOKING
            </span>

            <h3>
              Reserve Your Seat
            </h3>

            <p className="panel-description">
              Enter a unique passenger ID and
              compete for the currently available
              Tatkal inventory.
            </p>

            <label className="input-label">
              Passenger / User ID
            </label>

            <input
              className="user-input"
              value={userId}
              disabled={
                loading ||
                (reservation &&
                  reservation.status === "HELD")
              }
              onChange={(event) =>
                setUserId(event.target.value)
              }
              placeholder="Example: USER-001"
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  bookSeat();
                }
              }}
            />

            <button
              className="primary-button"
              onClick={bookSeat}
              disabled={
                loading ||
                (reservation &&
                  reservation.status === "HELD")
              }
            >
              <Zap size={19} />

              {loading
                ? "Processing..."
                : "Book Tatkal Now"}
            </button>

            <div className="security-note">
              <LockKeyhole size={17} />

              <span>
                Protected by PostgreSQL
                <strong>
                  {" "}
                  FOR UPDATE SKIP LOCKED
                </strong>
              </span>
            </div>
          </div>

          <div className="panel reservation-panel">
            <span className="eyebrow">
              YOUR RESERVATION
            </span>

            {!reservation ? (
              <div className="empty-reservation">
                <div className="empty-icon">
                  <Ticket size={31} />
                </div>

                <h3>
                  No Active Reservation
                </h3>

                <p>
                  Book a Tatkal seat to start
                  the payment countdown.
                </p>
              </div>
            ) : (
              <>
                <div className="reservation-header">
                  <div>
                    <small>
                      ALLOCATED SEAT
                    </small>

                    <strong>
                      {reservation.seat}
                    </strong>
                  </div>

                  <span
                    className={`reservation-status ${reservation.status.toLowerCase()}`}
                  >
                    {reservation.status}
                  </span>
                </div>

                <div className="reservation-details">
                  <div>
                    <span>User ID</span>

                    <strong>
                      {reservation.user_id}
                    </strong>
                  </div>

                  <div>
                    <span>
                      Queue Position
                    </span>

                    <strong>
                      #{reservation.queue_number}
                    </strong>
                  </div>

                  <div>
                    <span>
                      Reservation ID
                    </span>

                    <strong>
                      #{reservation.reservation_id}
                    </strong>
                  </div>
                </div>

                {reservation.status ===
                  "HELD" && (
                  <>
                    <div
                      className={`countdown ${
                        secondsLeft <= 10
                          ? "countdown-danger"
                          : ""
                      }`}
                    >
                      <small>
                        COMPLETE PAYMENT WITHIN
                      </small>

                      <strong>
                        00:
                        {String(
                          secondsLeft
                        ).padStart(2, "0")}
                      </strong>

                      <div className="countdown-track">
                        <div
                          className="countdown-progress"
                          style={{
                            width: `${Math.max(
                              0,
                              Math.min(
                                100,
                                (secondsLeft /
                                  (reservation.expires_in_seconds ||
                                    30)) *
                                  100
                              )
                            )}%`,
                          }}
                        ></div>
                      </div>
                    </div>

                    <div className="payment-actions">
                      <button
                        className="success-button"
                        onClick={
                          paymentSuccess
                        }
                        disabled={loading}
                      >
                        <CheckCircle2
                          size={18}
                        />

                        Payment Success
                      </button>

                      <button
                        className="failure-button"
                        onClick={
                          paymentFailure
                        }
                        disabled={loading}
                      >
                        <XCircle
                          size={18}
                        />

                        Payment Failure
                      </button>
                    </div>
                  </>
                )}

                {reservation.status ===
                  "BOOKED" && (
                  <div className="confirmed-box">
                    <CheckCircle2
                      size={27}
                    />

                    <div>
                      <strong>
                        Booking Confirmed
                      </strong>

                      <span>
                        Your Tatkal seat is
                        secured.
                      </span>
                    </div>
                  </div>
                )}

                {reservation.status ===
                  "BOOKED" && (
                  <button
                    className="secondary-button"
                    onClick={resetBooking}
                  >
                    New Booking
                  </button>
                )}
              </>
            )}
          </div>
        </section>

        {/* ====================================================
            QUEUE
        ==================================================== */}

        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">
                REQUEST ORDER
              </span>

              <h3>
                Live Tatkal Queue
              </h3>

              <p>
                Every booking request receives
                a unique queue identifier for
                ordering and audit.
              </p>
            </div>

            <div className="queue-total">
              <Users size={18} />

              {queue.length} Requests
            </div>
          </div>

          {recentQueue.length === 0 ? (
            <div className="queue-empty">
              No booking requests yet.
            </div>
          ) : (
            <div className="queue-table">
              <div className="queue-row queue-header">
                <span>QUEUE</span>
                <span>USER</span>
                <span>STATUS</span>
              </div>

              {recentQueue.map((item) => (
                <div
                  className="queue-row"
                  key={`${item.queue_number}-${item.user_id}`}
                >
                  <strong>
                    #{item.queue_number}
                  </strong>

                  <span>
                    {item.user_id}
                  </span>

                  <span
                    className={`queue-status ${item.status.toLowerCase()}`}
                  >
                    {item.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ====================================================
            LIVE CONCURRENCY SIMULATION
        ==================================================== */}

        <section className="concurrency-panel">
          <div className="concurrency-content">
            <div className="lightning-box">
              <Zap size={32} />
            </div>

            <span className="eyebrow light">
              LIVE CONCURRENCY ENGINE
            </span>

            <h3>
              Simulate the 10:00 AM Tatkal Rush
            </h3>

            <p>
              Launch 1,000 artificial booking
              requests against 10 isolated seats
              with 200 concurrent workers.
              PostgreSQL row locking protects
              every seat allocation.
            </p>

            <div className="architecture-tags">
              <span>
                <Database size={15} />
                PostgreSQL
              </span>

              <span>
                <LockKeyhole size={15} />
                Row Locking
              </span>

              <span>
                <Activity size={15} />
                200 Concurrent
              </span>

              <span>
                <ShieldCheck size={15} />
                Double-Booking Protection
              </span>
            </div>

            <button
              className="simulation-button"
              onClick={runRushSimulation}
              disabled={simulationLoading}
            >
              {simulationLoading ? (
                <>
                  <RefreshCw
                    size={19}
                    className="spin"
                  />

                  Simulating 1,000 Users...
                </>
              ) : (
                <>
                  <Zap size={19} />

                  Simulate 1,000 Users
                </>
              )}
            </button>

            <div className="simulation-note">
              <Database size={16} />

              <span>
                Uses isolated simulation tables.
                Your real T01–T10 inventory is
                not modified.
              </span>
            </div>
          </div>

          <div className="concurrency-proof">
            <span>
              {simulationResult
                ? "LIVE SIMULATION RESULT"
                : "READY FOR LIVE STRESS TEST"}
            </span>

            <div className="proof-number">
              {simulationConfig
                ? simulationConfig.artificial_users.toLocaleString()
                : "1,000"}
            </div>

            <small>
              ARTIFICIAL USERS
            </small>

            <div className="proof-grid">
              <div>
                <strong>
                  {simulationStats
                    ? simulationStats.successful_holds
                    : "10"}
                </strong>

                <span>Winners</span>
              </div>

              <div>
                <strong>
                  {simulationStats
                    ? simulationStats.rejected_requests
                    : "990"}
                </strong>

                <span>Rejected</span>
              </div>

              <div>
                <strong>
                  {simulationStats
                    ? simulationStats.duplicate_seat_allocations
                    : "0"}
                </strong>

                <span>Duplicates</span>
              </div>

              <div>
                <strong>
                  {simulationStats
                    ? simulationStats.request_errors
                    : "0"}
                </strong>

                <span>Errors</span>
              </div>
            </div>

            {simulationResult && (
              <>
                <div className="simulation-extra-grid">
                  <div>
                    <span>
                      Concurrency
                    </span>

                    <strong>
                      {
                        simulationConfig.concurrency
                      }
                    </strong>
                  </div>

                  <div>
                    <span>
                      Physical Seats
                    </span>

                    <strong>
                      {
                        simulationConfig.physical_seats
                      }
                    </strong>
                  </div>

                  <div>
                    <span>
                      Queue IDs
                    </span>

                    <strong>
                      {
                        simulationStats.queue_ids_issued
                      }
                    </strong>
                  </div>

                  <div>
                    <span>
                      Execution
                    </span>

                    <strong>
                      {
                        simulationStats.execution_time_seconds
                      }
                      s
                    </strong>
                  </div>
                </div>

                <div className="verification-list">
                  <div>
                    {simulationVerification.zero_double_booking ? (
                      <CheckCircle2
                        size={17}
                      />
                    ) : (
                      <XCircle size={17} />
                    )}

                    <span>
                      Zero Double Booking
                    </span>
                  </div>

                  <div>
                    {simulationVerification.unique_queue_ids ? (
                      <CheckCircle2
                        size={17}
                      />
                    ) : (
                      <XCircle size={17} />
                    )}

                    <span>
                      Unique Queue IDs
                    </span>
                  </div>

                  <div>
                    {simulationVerification.expected_winner_count ? (
                      <CheckCircle2
                        size={17}
                      />
                    ) : (
                      <XCircle size={17} />
                    )}

                    <span>
                      Expected Winner Count
                    </span>
                  </div>

                  <div>
                    {simulationVerification.no_request_errors ? (
                      <CheckCircle2
                        size={17}
                      />
                    ) : (
                      <XCircle size={17} />
                    )}

                    <span>
                      No Request Errors
                    </span>
                  </div>
                </div>

                <div className="simulation-seat-visual">
  <div className="simulation-seat-header">
    <div>
      <span>ISOLATED TEST INVENTORY</span>
      <strong>Simulation Seat Allocation</strong>
    </div>

    <div className="simulation-seat-count">
      {simulationResult.allocated_seats.length}/
      {simulationConfig.physical_seats}
    </div>
  </div>

  <div className="simulation-seat-grid">
    {Array.from(
      { length: simulationConfig.physical_seats },
      (_, index) => {
        const seat = `SIM-${String(index + 1).padStart(2, "0")}`;

        const allocated =
          simulationResult.allocated_seats.includes(seat);

        return (
          <div
            key={seat}
            className={`simulation-seat ${
              allocated ? "simulation-seat-winner" : ""
            }`}
          >
            <div className="simulation-seat-icon">
              {allocated ? (
                <CheckCircle2 size={18} />
              ) : (
                <Ticket size={18} />
              )}
            </div>

            <strong>{seat}</strong>

            <span>
              {allocated ? "WINNER" : "AVAILABLE"}
            </span>
          </div>
        );
      }
    )}
  </div>

  <div className="simulation-isolation-note">
    <ShieldCheck size={16} />

    <span>
      Isolated stress-test inventory — your real T01–T10
      booking seats are unchanged.
    </span>
  </div>
</div>
              </>
            )}

            <div
              className={`consistency-pass ${
                simulationVerification?.consistency ===
                "FAIL"
                  ? "consistency-fail"
                  : ""
              }`}
            >
              {simulationVerification?.consistency ===
              "FAIL" ? (
                <XCircle size={20} />
              ) : (
                <ShieldCheck size={20} />
              )}

              <div>
                <strong>
                  {simulationLoading
                    ? "SIMULATION RUNNING"
                    : simulationVerification
                    ? `CONSISTENCY ${simulationVerification.consistency}`
                    : "SYSTEM READY"}
                </strong>

                <span>
                  {simulationLoading
                    ? "Processing concurrent PostgreSQL transactions..."
                    : simulationStats
                    ? `${simulationStats.successful_holds} winners from ${simulationStats.total_requests.toLocaleString()} requests`
                    : "Run the live concurrency test"}
                </span>
              </div>
            </div>
          </div>
        </section>
        {/* ====================================================
    SYSTEM ARCHITECTURE
==================================================== */}

<section className="architecture-section">
  <div className="architecture-heading">
    <span className="eyebrow">
      TECHNICAL ARCHITECTURE
    </span>

    <h3>How Tatkal Rush Prevents Double Booking</h3>

    <p>
      Every booking request passes through a concurrency-safe
      transaction flow before a seat can be allocated.
    </p>
  </div>

  <div className="architecture-flow">
    <div className="architecture-node">
      <div className="architecture-node-icon">
        <Users size={24} />
      </div>

      <strong>1,000 Users</strong>
      <span>Rush Traffic</span>
    </div>

    <div className="architecture-arrow">→</div>

    <div className="architecture-node">
      <div className="architecture-node-icon">
        <Activity size={24} />
      </div>

      <strong>React Client</strong>
      <span>Booking Requests</span>
    </div>

    <div className="architecture-arrow">→</div>

    <div className="architecture-node">
      <div className="architecture-node-icon">
        <Zap size={24} />
      </div>

      <strong>FastAPI</strong>
      <span>Async API Layer</span>
    </div>

    <div className="architecture-arrow">→</div>

    <div className="architecture-node architecture-node-important">
      <div className="architecture-node-icon">
        <Database size={24} />
      </div>

      <strong>PostgreSQL</strong>
      <span>Transactional Database</span>
    </div>

    <div className="architecture-arrow">→</div>

    <div className="architecture-node architecture-node-lock">
      <div className="architecture-node-icon">
        <LockKeyhole size={24} />
      </div>

      <strong>Row Lock</strong>
      <span>SKIP LOCKED</span>
    </div>

    <div className="architecture-arrow">→</div>

    <div className="architecture-node">
      <div className="architecture-node-icon">
        <Ticket size={24} />
      </div>

      <strong>10 Seats</strong>
      <span>Safe Allocation</span>
    </div>
  </div>

  <div className="architecture-lock-proof">
    <div className="lock-proof-icon">
      <LockKeyhole size={26} />
    </div>

    <div>
      <span>CORE CONCURRENCY CONTROL</span>

      <code>FOR UPDATE SKIP LOCKED</code>

      <p>
        A transaction locks the selected available seat.
        Concurrent transactions skip already locked rows instead
        of allocating the same seat twice.
      </p>
    </div>

    <div className="lock-proof-result">
      <CheckCircle2 size={22} />

      <div>
        <strong>0</strong>
        <span>DOUBLE BOOKINGS</span>
      </div>
    </div>
  </div>

  <div className="architecture-systems">
    <div className="architecture-system-card">
      <div className="system-card-heading">
        <Ticket size={21} />

        <div>
          <span>REAL BOOKING FLOW</span>
          <strong>T01 – T10</strong>
        </div>
      </div>

      <div className="system-flow-list">
        <span>01</span>
        <p>User submits booking request</p>

        <span>02</span>
        <p>Available seat is transactionally locked</p>

        <span>03</span>
        <p>Seat enters HELD state</p>

        <span>04</span>
        <p>Payment countdown begins</p>

        <span>05</span>
        <p>Success → BOOKED</p>

        <span>06</span>
        <p>Failure / timeout → AVAILABLE</p>
      </div>
    </div>

    <div className="architecture-system-card simulation-system-card">
      <div className="system-card-heading">
        <Zap size={21} />

        <div>
          <span>ISOLATED STRESS TEST</span>
          <strong>SIM-01 – SIM-10</strong>
        </div>
      </div>

      <div className="system-metric-row">
        <div>
          <strong>1,000</strong>
          <span>Requests</span>
        </div>

        <div>
          <strong>200</strong>
          <span>Concurrent</span>
        </div>

        <div>
          <strong>10</strong>
          <span>Winners</span>
        </div>

        <div>
          <strong>990</strong>
          <span>Rejected</span>
        </div>
      </div>

      <div className="system-proof-list">
        <div>
          <CheckCircle2 size={16} />
          Unique Queue IDs
        </div>

        <div>
          <CheckCircle2 size={16} />
          Zero Duplicate Seats
        </div>

        <div>
          <CheckCircle2 size={16} />
          Database Verification
        </div>

        <div>
          <CheckCircle2 size={16} />
          Isolated From Real Inventory
        </div>
      </div>
    </div>
  </div>

  <div className="architecture-final-proof">
    <ShieldCheck size={30} />

    <div>
      <span>CONCURRENCY SAFETY</span>
      <strong>ZERO DOUBLE BOOKING</strong>

      <p>
        Seat allocation is protected at the database transaction
        layer rather than relying only on frontend checks.
      </p>
    </div>
  </div>
  
</section>
        {/* ====================================================
            PERFORMANCE DASHBOARD
        ==================================================== */}

        <section className="performance-section">
          <div className="performance-heading">
            <div>
              <span className="eyebrow">
                ENGINEERING METRICS
              </span>

              <h3>System Performance</h3>

              <p>
                Real measurements from the latest isolated
                concurrency simulation.
              </p>
            </div>

            <div
              className={`performance-status ${
                simulationResult ? "performance-status-live" : ""
              }`}
            >
              <Activity size={17} />

              {simulationResult
                ? "LIVE RESULT"
                : "WAITING FOR TEST"}
            </div>
          </div>

          {!simulationResult ? (
            <div className="performance-empty">
              <div className="performance-empty-icon">
                <Activity size={30} />
              </div>

              <h4>No simulation result yet</h4>

              <p>
                Run the 1,000-user concurrency simulation above
                to populate real performance measurements.
              </p>
            </div>
          ) : (
            <>
              <div className="performance-grid">
                <div className="performance-card">
                  <div className="performance-card-icon">
                    <Users size={22} />
                  </div>

                  <span>TOTAL REQUESTS</span>

                  <strong>
                    {simulationStats.total_requests.toLocaleString()}
                  </strong>

                  <small>
                    Artificial booking attempts
                  </small>
                </div>

                <div className="performance-card">
                  <div className="performance-card-icon">
                    <Activity size={22} />
                  </div>

                  <span>CONCURRENCY</span>

                  <strong>
                    {simulationConfig.concurrency}
                  </strong>

                  <small>
                    Concurrent workers
                  </small>
                </div>

                <div className="performance-card">
                  <div className="performance-card-icon">
                    <Ticket size={22} />
                  </div>

                  <span>SUCCESSFUL HOLDS</span>

                  <strong>
                    {simulationStats.successful_holds}
                  </strong>

                  <small>
                    From {simulationConfig.physical_seats} seats
                  </small>
                </div>

                <div className="performance-card">
                  <div className="performance-card-icon">
                    <Clock3 size={22} />
                  </div>

                  <span>EXECUTION TIME</span>

                  <strong>
                    {simulationStats.execution_time_seconds}s
                  </strong>

                  <small>
                    End-to-end simulation
                  </small>
                </div>

                <div className="performance-card performance-safe">
                  <div className="performance-card-icon">
                    <ShieldCheck size={22} />
                  </div>

                  <span>DUPLICATE SEATS</span>

                  <strong>
                    {simulationStats.duplicate_seat_allocations}
                  </strong>

                  <small>
                    Double bookings detected
                  </small>
                </div>

                <div className="performance-card performance-safe">
                  <div className="performance-card-icon">
                    <Database size={22} />
                  </div>

                  <span>REQUEST ERRORS</span>

                  <strong>
                    {simulationStats.request_errors}
                  </strong>

                  <small>
                    Processing failures
                  </small>
                </div>
              </div>

              <div className="performance-summary">
                <div className="performance-summary-icon">
                  <ShieldCheck size={30} />
                </div>

                <div className="performance-summary-text">
                  <span>CONCURRENCY VERIFICATION</span>

                  <strong>
                    {simulationVerification.consistency === "PASS"
                      ? "SYSTEM PASSED"
                      : "CHECK REQUIRED"}
                  </strong>

                  <p>
                    {simulationStats.total_requests.toLocaleString()} requests
                    competed for {simulationConfig.physical_seats} seats with{" "}
                    {simulationConfig.concurrency} concurrent workers.
                  </p>
                </div>

                <div className="performance-summary-results">
                  <div>
                    <CheckCircle2 size={16} />

                    <span>
                      {simulationStats.successful_holds} Winners
                    </span>
                  </div>

                  <div>
                    <CheckCircle2 size={16} />

                    <span>
                      {simulationStats.rejected_requests} Rejected
                    </span>
                  </div>

                  <div>
                    <CheckCircle2 size={16} />

                    <span>
                      {simulationStats.duplicate_seat_allocations} Duplicates
                    </span>
                  </div>

                  <div>
                    <CheckCircle2 size={16} />

                    <span>
                      {simulationStats.request_errors} Errors
                    </span>
                  </div>
                </div>
              </div>
            </>
          )}
        </section>
      </main>

      {/* ======================================================
          MESSAGE TOAST
      ====================================================== */}

      {message && (
        <div
          className={`toast ${messageType}`}
        >
          {messageType === "success" ? (
            <CheckCircle2 size={20} />
          ) : (
            <XCircle size={20} />
          )}

          <span>
            {message}
          </span>

          <button
            onClick={() =>
              setMessage("")
            }
          >
            ×
          </button>
        </div>
      )}

      {/* ======================================================
          FOOTER
      ====================================================== */}

      <footer>
        <div>
          <TrainFront size={20} />

          <strong>
            Tatkal Rush
          </strong>
        </div>

        <span>
          Concurrency-Safe Railway Booking
          Prototype
        </span>
      </footer>
    </div>
  );
}

export default App;
