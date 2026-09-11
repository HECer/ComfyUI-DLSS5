# Glossary and context-map format

## GLOSSARY.md

```md
# Glossary

## Ordering

**Order**
: A customer's confirmed request for one or more products.
  _Avoid_: Purchase, transaction

**Cancellation**
: The reversal of an entire Order before fulfillment begins.
  _Avoid_: Refund, deletion
```

Keep each definition to one or two sentences. Define what the term is, name aliases to avoid, and
include only concepts specific to this project's domain. Group terms when natural clusters emerge.

## CONTEXT-MAP.md

Create this optional file only for multiple domain contexts:

```md
# Context Map

## Contexts

- **Ordering**: receives and tracks customer orders
- **Billing**: issues invoices and processes payments

## Relationships

- **Ordering -> Billing**: Ordering emits `OrderConfirmed`; Billing creates an invoice.
```

Name ownership and the observable relationship. Do not turn the map into an implementation dump.
