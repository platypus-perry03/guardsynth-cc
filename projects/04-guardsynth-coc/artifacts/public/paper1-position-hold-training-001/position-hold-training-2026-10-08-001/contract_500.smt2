; benchmark generated from python API
(set-info :status unknown)
(declare-fun position_hold_500__y_0__const () Int)
(declare-fun position_hold_500__x_0__const () Int)
(declare-fun position_hold_500__y_1__const () Int)
(declare-fun position_hold_500__x_1__const () Int)
(declare-fun position_hold_500__y_2__const () Int)
(declare-fun position_hold_500__x_2__const () Int)
(assert
 (let ((?x21 (+ (* position_hold_500__x_0__const position_hold_500__x_0__const) (* position_hold_500__y_0__const position_hold_500__y_0__const))))
 (>= 40000 ?x21)))
(assert
 (let ((?x26 (+ (* position_hold_500__x_1__const position_hold_500__x_1__const) (* position_hold_500__y_1__const position_hold_500__y_1__const))))
 (>= 40000 ?x26)))
(assert
 (let ((?x30 (+ (* position_hold_500__x_2__const position_hold_500__x_2__const) (* position_hold_500__y_2__const position_hold_500__y_2__const))))
(>= 40000 ?x30)))
(check-sat)
