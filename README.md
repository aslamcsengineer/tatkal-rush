# 🚆 Tatkal Rush

### High-Concurrency Railway Booking System

Tatkal Rush is a full-stack railway booking prototype designed to demonstrate how a booking system can safely handle extreme concurrent traffic without allocating the same seat to multiple users.

The project simulates a Tatkal-style booking rush using **React, FastAPI, PostgreSQL, and database-level row locking**.

---

## 🎯 Problem

High-demand booking systems can receive thousands of requests for a very small inventory at nearly the same time.

Without proper concurrency control, multiple requests may attempt to reserve the same seat, resulting in:

- Double booking
- Inconsistent inventory
- Race conditions
- Unfair seat allocation
- Failed or conflicting reservations

Tatkal Rush demonstrates a concurrency-safe approach to this problem.

---

## ✨ Features

### Real Booking Flow

- Live Tatkal seat inventory
- T01–T10 physical demo seats
- Unique queue number for every request
- Concurrency-safe seat allocation
- Temporary seat hold
- Payment countdown
- Payment success → `BOOKED`
- Payment failure → seat released
- Automatic hold expiry
- Live inventory refresh
- Booking statistics

### High-Concurrency Simulation

The application also contains an isolated stress-test environment.

A single click can simulate:

- **1,000 artificial users**
- **200 concurrent workers**
- **10 simulation seats**
- Unique queue IDs
- Database-level concurrency protection
- Duplicate-seat verification
- Request-error verification

The simulation inventory is isolated from the real T01–T10 booking inventory.

---

## 🧪 Latest Stress-Test Result

A local simulation produced:

| Metric | Result |
|---|---:|
| Total requests | 1,000 |
| Concurrent workers | 200 |
| Physical simulation seats | 10 |
| Successful allocations | 10 |
| Rejected requests | 990 |
| Duplicate seat allocations | 0 |
| Duplicate queue IDs | 0 |
| Request errors | 0 |
| Execution time | 1.67 seconds |
| Consistency | PASS |

> Execution time depends on the machine and runtime environment. The application displays the actual result returned by each simulation run.

### Result

**10 seats → 10 winners → 990 rejected → 0 double bookings**

---

## 🔐 Concurrency Strategy

The core booking flow uses PostgreSQL transactional row locking.

```sql
FOR UPDATE SKIP LOCKED
```

When one transaction selects and locks an available seat, concurrent transactions skip that locked row instead of attempting to allocate the same seat.

Conceptually:

```text
Concurrent booking requests
            │
            ▼
         FastAPI
            │
            ▼
      PostgreSQL transaction
            │
            ▼
   SELECT available seat
   FOR UPDATE SKIP LOCKED
            │
            ▼
       Lock one seat
            │
            ▼
     Create reservation
```

This protects seat allocation at the database transaction layer rather than relying only on frontend state.

---

## 🏗️ Architecture

```text
                  ┌─────────────────┐
                  │   React Client  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │     FastAPI     │
                  │    REST API     │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   PostgreSQL    │
                  │  Transactions   │
                  └────────┬────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │ FOR UPDATE SKIP LOCKED  │
              └────────────┬────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Safe Allocation │
                  └─────────────────┘
```

---

## 🔄 Two Separate Inventories

Tatkal Rush intentionally separates normal booking from stress testing.

### Real Booking Inventory

```text
T01 – T10

User
 ↓
Booking request
 ↓
Seat HELD
 ↓
Payment countdown
 ├── Success → BOOKED
 └── Failure / Timeout → AVAILABLE
```

### Isolated Simulation Inventory

```text
SIM-01 – SIM-10

1,000 Requests
      ↓
200 Concurrent Workers
      ↓
PostgreSQL Concurrency Control
      ↓
10 Winners
990 Rejected
0 Duplicate Allocations
```

This allows the stress simulation to run without modifying the real booking demonstration.

---

## 🛠️ Technology Stack

### Frontend

- React
- Vite
- JavaScript
- CSS
- Lucide React

### Backend

- Python
- FastAPI
- Uvicorn

### Database

- PostgreSQL
- Transactional row locking
- `FOR UPDATE SKIP LOCKED`

### Testing

- Python concurrency simulation
- 1,000 artificial booking requests
- 200 concurrent workers
- Database consistency verification

---

## 📡 API

Main endpoints include:

```text
GET  /health
GET  /seats

POST /book

POST /payment/{reservation_id}/success
POST /payment/{reservation_id}/failure

POST /expire

GET  /queue
GET  /stats

POST /simulate-rush
```

FastAPI also provides interactive OpenAPI documentation through `/docs` when the backend is running.

---

## 📁 Project Structure

```text
tatkal-rush/
│
├── backend/
│   ├── database.py
│   ├── main.py
│   ├── setup_db.py
│   ├── load_test.py
│   ├── rush_test.py
│   └── simulation.py
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── index.css
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
│
├── .gitignore
└── README.md
```

---

## 💻 Running Locally

### Requirements

Install:

- Python
- PostgreSQL
- Node.js
- npm

---

### 1. Clone the repository

```bash
git clone https://github.com/aslamcsengineer/tatkal-rush.git
cd tatkal-rush
```

---

### 2. Backend setup

```bash
cd backend

python -m venv venv
```

Windows:

```powershell
venv\Scripts\activate
```

Install the backend dependencies required by the project.

Configure your PostgreSQL connection using your local environment variables.

> Never commit database passwords or `.env` files to GitHub.

Initialize the demo database if required:

```bash
python setup_db.py
```

Start FastAPI:

```bash
uvicorn main:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

---

### 3. Frontend setup

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

## 🖥️ Application Dashboard

The frontend includes:

- Railway-style booking interface
- Live T01–T10 inventory
- Booking queue
- Reservation countdown
- Payment controls
- Automatic seat release
- Live concurrency simulation
- SIM-01–SIM-10 allocation visualization
- Technical architecture visualization
- Engineering performance dashboard

---

## 🧠 Engineering Concepts Demonstrated

This project demonstrates practical concepts including:

- Race conditions
- Database transactions
- Row-level locking
- Concurrent request handling
- Inventory consistency
- Temporary reservations
- Booking expiry
- Queue identifiers
- Stress testing
- API design
- Full-stack integration

---

## 🔮 Future Improvements

Potential extensions include:

- Admin Control Center
- Visual seat release/cancellation
- Authentication and authorization
- Admin/user roles
- Redis-based queueing
- Distributed locking
- Multiple trains and travel dates
- Passenger details
- Payment gateway integration
- Monitoring and observability
- Docker deployment
- Horizontal backend scaling

---

## ⚠️ Project Scope

Tatkal Rush is an educational engineering prototype inspired by high-concurrency railway booking scenarios.

It is **not affiliated with IRCTC or Indian Railways** and is not intended to represent or reproduce their production infrastructure.

---

## 👨‍💻 Author

**Mohammed Aslam**

GitHub: `aslamcsengineer`

---

## ⭐ Project Goal

The central engineering objective is simple:

> Handle intense competition for limited inventory while maintaining database consistency and preventing double booking.

**1,000 requests. 10 seats. 0 duplicate allocations.**