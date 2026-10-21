; benchmark generated from python API
(set-info :status unknown)
(declare-fun pair_z1_m1__signal_s1_truth__t0 () Int)
(declare-fun pair_z1_m1__signal_s1_truth__t1 () Int)
(declare-fun pair_z1_m1__cross_a_truth__t0 () Int)
(declare-fun pair_z1_m1__cross_a_truth__t1 () Int)
(declare-fun pair_z1_m1__action__t0 () Int)
(declare-fun pair_z1_m1__action__t1 () Int)
(declare-fun pair_z1_m1__signal_s1_evidence_valid__t0 () Bool)
(declare-fun pair_z1_m1__signal_s1_on__t0 () Bool)
(declare-fun pair_z1_m1__signal_s1_evidence_valid__t1 () Bool)
(declare-fun pair_z1_m1__signal_s1_on__t1 () Bool)
(declare-fun pair_z1_m1__signal_s1_clear__t0 () Bool)
(declare-fun pair_z1_m1__signal_s1_clear__t1 () Bool)
(declare-fun pair_z1_m1__signal_s1_prior_active__const () Bool)
(declare-fun pair_z1_m1__signal_s1_active__t0 () Bool)
(declare-fun pair_z1_m1__signal_s1_active__t1 () Bool)
(declare-fun pair_z1_m1__cross_a_evidence_valid__t0 () Bool)
(declare-fun pair_z1_m1__cross_a_on__t0 () Bool)
(declare-fun pair_z1_m1__cross_a_evidence_valid__t1 () Bool)
(declare-fun pair_z1_m1__cross_a_on__t1 () Bool)
(declare-fun pair_z1_m1__cross_a_clear__t0 () Bool)
(declare-fun pair_z1_m1__cross_a_clear__t1 () Bool)
(declare-fun pair_z1_m1__cross_a_prior_active__const () Bool)
(declare-fun pair_z1_m1__cross_a_active__t0 () Bool)
(declare-fun pair_z1_m1__cross_a_active__t1 () Bool)
(declare-fun pair_z1_m1__entry_permitted__t0 () Bool)
(declare-fun pair_z1_m1__entry_permitted__t1 () Bool)
(declare-fun pair_z1_m1__review_required__t0 () Bool)
(declare-fun pair_z1_m1__review_required__t1 () Bool)
(declare-fun pair_z1_m1__ego_inside_z1__t0 () Bool)
(declare-fun pair_z1_m1__ego_inside_z1__t1 () Bool)
(assert
 (let (($x9 (<= pair_z1_m1__signal_s1_truth__t0 3)))
 (let (($x7 (>= pair_z1_m1__signal_s1_truth__t0 0)))
 (and $x7 $x9))))
(assert
 (let (($x13 (<= pair_z1_m1__signal_s1_truth__t1 3)))
 (let (($x12 (>= pair_z1_m1__signal_s1_truth__t1 0)))
 (and $x12 $x13))))
(assert
 (let (($x26 (<= pair_z1_m1__cross_a_truth__t0 3)))
 (let (($x25 (>= pair_z1_m1__cross_a_truth__t0 0)))
 (and $x25 $x26))))
(assert
 (let (($x30 (<= pair_z1_m1__cross_a_truth__t1 3)))
 (let (($x29 (>= pair_z1_m1__cross_a_truth__t1 0)))
 (and $x29 $x30))))
(assert
 (let (($x48 (<= pair_z1_m1__action__t0 1)))
 (let (($x46 (>= pair_z1_m1__action__t0 0)))
 (and $x46 $x48))))
(assert
 (let (($x52 (<= pair_z1_m1__action__t1 1)))
 (let (($x51 (>= pair_z1_m1__action__t1 0)))
 (and $x51 $x52))))
(assert
 (let (($x56 (= 0 pair_z1_m1__signal_s1_truth__t0)))
 (= pair_z1_m1__signal_s1_on__t0 (and pair_z1_m1__signal_s1_evidence_valid__t0 $x56))))
(assert
 (let (($x60 (and pair_z1_m1__signal_s1_evidence_valid__t1 (= 0 pair_z1_m1__signal_s1_truth__t1))))
 (= pair_z1_m1__signal_s1_on__t1 $x60)))
(assert
 (let (($x63 (and pair_z1_m1__signal_s1_evidence_valid__t0 (= 1 pair_z1_m1__signal_s1_truth__t0))))
 (= pair_z1_m1__signal_s1_clear__t0 $x63)))
(assert
 (let (($x65 (= 1 pair_z1_m1__signal_s1_truth__t1)))
 (= pair_z1_m1__signal_s1_clear__t1 (and pair_z1_m1__signal_s1_evidence_valid__t1 $x65))))
(assert
 (let (($x68 (ite pair_z1_m1__signal_s1_clear__t0 false pair_z1_m1__signal_s1_prior_active__const)))
 (= pair_z1_m1__signal_s1_active__t0 (ite pair_z1_m1__signal_s1_on__t0 true $x68))))
(assert
 (let (($x71 (ite pair_z1_m1__signal_s1_clear__t1 false pair_z1_m1__signal_s1_active__t0)))
 (= pair_z1_m1__signal_s1_active__t1 (ite pair_z1_m1__signal_s1_on__t1 true $x71))))
(assert
 (let (($x74 (and (distinct 1 pair_z1_m1__action__t0) true)))
 (=> pair_z1_m1__signal_s1_active__t0 $x74)))
(assert
 (let (($x76 (and (distinct 1 pair_z1_m1__action__t1) true)))
 (=> pair_z1_m1__signal_s1_active__t1 $x76)))
(assert
 (let (($x78 (= 0 pair_z1_m1__cross_a_truth__t0)))
 (= pair_z1_m1__cross_a_on__t0 (and pair_z1_m1__cross_a_evidence_valid__t0 $x78))))
(assert
 (let (($x81 (= 0 pair_z1_m1__cross_a_truth__t1)))
 (= pair_z1_m1__cross_a_on__t1 (and pair_z1_m1__cross_a_evidence_valid__t1 $x81))))
(assert
 (let (($x85 (and pair_z1_m1__cross_a_evidence_valid__t0 (= 1 pair_z1_m1__cross_a_truth__t0))))
 (= pair_z1_m1__cross_a_clear__t0 $x85)))
(assert
 (let (($x88 (and pair_z1_m1__cross_a_evidence_valid__t1 (= 1 pair_z1_m1__cross_a_truth__t1))))
 (= pair_z1_m1__cross_a_clear__t1 $x88)))
(assert
 (let (($x90 (ite pair_z1_m1__cross_a_clear__t0 false pair_z1_m1__cross_a_prior_active__const)))
 (= pair_z1_m1__cross_a_active__t0 (ite pair_z1_m1__cross_a_on__t0 true $x90))))
(assert
 (let (($x93 (ite pair_z1_m1__cross_a_clear__t1 false pair_z1_m1__cross_a_active__t0)))
 (= pair_z1_m1__cross_a_active__t1 (ite pair_z1_m1__cross_a_on__t1 true $x93))))
(assert
 (let (($x74 (and (distinct 1 pair_z1_m1__action__t0) true)))
 (=> pair_z1_m1__cross_a_active__t0 $x74)))
(assert
 (let (($x76 (and (distinct 1 pair_z1_m1__action__t1) true)))
 (=> pair_z1_m1__cross_a_active__t1 $x76)))
(assert
 (= pair_z1_m1__entry_permitted__t0 (and pair_z1_m1__signal_s1_clear__t0 pair_z1_m1__cross_a_clear__t0)))
(assert
 (= pair_z1_m1__entry_permitted__t1 (and pair_z1_m1__signal_s1_clear__t1 pair_z1_m1__cross_a_clear__t1)))
(assert
 (let (($x107 (not pair_z1_m1__cross_a_evidence_valid__t0)))
 (let (($x110 (or $x107 (= 2 pair_z1_m1__cross_a_truth__t0) (= 3 pair_z1_m1__cross_a_truth__t0))))
 (let (($x102 (not pair_z1_m1__signal_s1_evidence_valid__t0)))
 (let (($x106 (or $x102 (= 2 pair_z1_m1__signal_s1_truth__t0) (= 3 pair_z1_m1__signal_s1_truth__t0))))
 (= pair_z1_m1__review_required__t0 (or $x106 $x110)))))))
(assert
 (let (($x117 (not pair_z1_m1__cross_a_evidence_valid__t1)))
 (let (($x120 (or $x117 (= 2 pair_z1_m1__cross_a_truth__t1) (= 3 pair_z1_m1__cross_a_truth__t1))))
 (let (($x113 (not pair_z1_m1__signal_s1_evidence_valid__t1)))
 (let (($x116 (or $x113 (= 2 pair_z1_m1__signal_s1_truth__t1) (= 3 pair_z1_m1__signal_s1_truth__t1))))
 (= pair_z1_m1__review_required__t1 (or $x116 $x120)))))))
(assert
 (let (($x123 (= 1 pair_z1_m1__action__t0)))
 (=> $x123 pair_z1_m1__entry_permitted__t0)))
(assert
 (let (($x125 (= 1 pair_z1_m1__action__t1)))
 (=> $x125 pair_z1_m1__entry_permitted__t1)))
(assert
 (= pair_z1_m1__signal_s1_prior_active__const false))
(assert
 (= 0 pair_z1_m1__signal_s1_truth__t0))
(assert
 (= pair_z1_m1__signal_s1_evidence_valid__t0 true))
(assert
 (= 1 pair_z1_m1__signal_s1_truth__t1))
(assert
 (= pair_z1_m1__signal_s1_evidence_valid__t1 true))
(assert
 (= pair_z1_m1__cross_a_prior_active__const false))
(assert
 (= 0 pair_z1_m1__cross_a_truth__t0))
(assert
 (= pair_z1_m1__cross_a_evidence_valid__t0 true))
(assert
 (= 0 pair_z1_m1__cross_a_truth__t1))
(assert
 (= pair_z1_m1__cross_a_evidence_valid__t1 true))
(assert
 (= pair_z1_m1__ego_inside_z1__t0 false))
(assert
 (= pair_z1_m1__ego_inside_z1__t1 (or pair_z1_m1__ego_inside_z1__t0 (= 1 pair_z1_m1__action__t1))))
(check-sat)
