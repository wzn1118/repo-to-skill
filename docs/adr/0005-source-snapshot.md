# ADR 0005: Separate Git Identity From Analysis Identity

Status: accepted

A Snapshot stores a requested ref, resolved commit, Git object format, dirty state, scan policy, and
policy-filtered analysis tree hash. Clean Git Evidence carries commit and blob identity. Dirty local
Evidence carries content/blob identity but not a false commit assertion. Sensitive paths can affect
the aggregate analysis-tree cache key without exposing their values or individual hashes.
