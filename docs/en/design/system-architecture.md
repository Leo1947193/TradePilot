# Main Request Process

```text
User Input (ticker)
-> Request Validation
-> Data Retrieval and Normalization
-> Parallel Analysis Modules
   - Fundamentals Analysis
   - Technical Analysis
   - Sentiment Analysis
   - Event Detection
-> Decision Synthesis
-> Trade Plan Generation
-> Storage / Review
```

## Boundary Notes

- Analysis modules produce domain-specific intermediate signals.
- Decision Synthesis is the only layer that assigns the final system-level decision label.
- Trade Plan Generation consumes module outputs and produces bullish and bearish scenario drafts.
