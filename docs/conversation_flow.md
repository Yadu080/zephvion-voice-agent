# Day 1 Conversation Flow — AI Call Answering + Booking + Lead Capture

## Scope for this MVP
One inbound call flow only. The agent must be able to:
1. Greet the caller and understand why they're calling.
2. Route to one of two paths: **book an appointment** or **general enquiry / lead capture**.
3. Handle a caller who wants a human (escalation message, no real transfer yet).

## Flow

```
Call connects
  -> Agent greets caller, asks how it can help
  -> Caller states intent
      -> INTENT: book/reschedule/cancel appointment
          -> Ask what service/reason for the appointment
          -> Ask preferred date/time
          -> [Day 2] call check_availability
          -> If available: confirm slot, [Day 2] call book_appointment
          -> If not available: offer next open slots
          -> Confirm booking details back to caller
          -> Ask if anything else is needed -> close call
      -> INTENT: general enquiry / wants information
          -> Ask clarifying questions to understand the need
          -> Capture name, phone/callback number, and requirement
          -> [Day 2] call capture_lead
          -> Tell caller they'll be followed up / confirm next step
          -> Close call
      -> INTENT: wants to speak to a human / complex request
          -> Acknowledge, explain a team member will follow up
          -> Capture name + callback number
          -> [Day 2] call capture_lead (flagged as "needs human")
          -> Close call
  -> Caller silent / hangs up
      -> Agent ends call gracefully after brief prompt, no error
```

## Fields to capture per call (structured data)
- caller_name
- callback_number
- intent (booking / enquiry / escalation)
- requested_service (if booking)
- requested_datetime (if booking)
- booking_confirmed (bool)
- notes / free-text summary

These map directly to the `capture_lead` and `book_appointment` tool calls built on Day 2.
