# AI & ML Department Lab Handbook (sample internal document)

This handbook describes the rules of the Department of CSE (AI & ML) Deep Learning Lab. It is an internal document and is not published on the web, which makes it a good test of whether the RAG system answers from its local knowledge base.

## Lab timings

The Deep Learning Lab is open from 9:00 AM to 8:00 PM on weekdays and from 10:00 AM to 4:00 PM on Saturdays. The lab is closed on Sundays and on university holidays. Students working on final-year projects may request extended access until 10:00 PM by emailing the lab in-charge at least one day in advance.

## GPU server booking rules

The lab has one shared GPU server called Tensor-1 with four NVIDIA RTX A6000 cards (48 GB each). GPU time must be booked through the department booking form.

- A single booking can be at most 8 hours long.
- Each project team can book at most 24 GPU-hours per week.
- A team may use at most two GPUs at the same time unless the lab in-charge approves more.
- Unused bookings must be cancelled at least 2 hours before the slot starts; teams that miss three slots without cancelling lose booking rights for one week.
- Training jobs longer than 2 hours must run inside tmux or screen so that they survive disconnections.

## Storage and data

Each team receives 200 GB of storage under /data/teams/<team-name>. Datasets larger than 50 GB must be placed in the shared read-only dataset folder by the lab assistant. Personal data, scraped data that violates a website's terms, and copyrighted media must not be stored on lab machines.

## Mini project reviews (third year)

Third-year mini projects are evaluated in three reviews:

1. Review 1 — idea presentation: problem statement, literature survey, proposed architecture and methodology.
2. Review 2 — implementation progress: at least 50% of the system working, with a baseline result.
3. Review 3 — final demonstration, evaluation results and the project report.

The marks split is 20% for Review 1, 30% for Review 2 and 50% for Review 3. Every team must keep its code in a version-controlled repository and show the commit history during Review 2.

## Contact

Technical issues with Tensor-1 are reported through the lab ticket form. Booking disputes are resolved by the lab in-charge.
