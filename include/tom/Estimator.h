namespace tom {

SWIGCODE(%feature("python:slot", "tp_repr", functype="reprfunc") Estimator::repr;)

/**
 * This class computes estimates for \f$f( x )\f$ and corresponding variance estimates for sequences \f$x\f$ based on a suffix tree representation of a sample sequence.
 */
class Estimator {
public:
    /**
     * Create an `Estimator` for a sample sequence data given by a suffix tree representation `stree`. */
    Estimator(const std::shared_ptr<stree::STree> &stree) : stree_(stree), state_(*this) {
        nO_ = stree_->sequence().nOutputSymbols();
        nU_ = stree_->sequence().nInputSymbols();
        N_ = (stree_->sequence().length());
        regularization("default");
    }

    /** Return the data sequence. */
    Sequence sequence() const {
        return stree_->sequence();
    }

    //<editor-fold desc="Estimates by f, v and fv">
    /**
     * Return an estimate of f( `z` ) for the given output symbol `z`. */
    double f(Symbol z) throw(std::invalid_argument) {
        if (nU_ != 0) throw std::invalid_argument("input symbol required");
        return (state_.reset(false) << z).f();
    }

    /**
     * Return an estimate of f( z ) for the given input-output symbol pair z = (`u`, `o`). In the case of an output-only system, the input `u` is simply ignored. */
    double f(Symbol o, Symbol u) { return (state_.reset(false) << std::make_pair(o,u)).f(); }

    /**
     * Return an estimate of f( `sequence` ). */
    double f(const Sequence &sequence) { return (state_.reset() << sequence).f(); }

    /**
     * Return the matrix of estimates for \f$[ f( x y ) ]_{y \in X, x \in X}\f$ with rows indexed by the given set `Y` of characteristic sequences and columns indexed by the given set `X` of indicative sequences. */
    MatrixXd f(const Sequences &Y, const Sequences &X) { return f(Y, Sequence(0, nO_, nU_), X); }

    /**
     * Return the matrix of estimates for \f$[ f( x z y ) ]_{y \in X, x \in X}\f$ with rows indexed by the given set `Y` of characteristic sequences and columns indexed by the given set `X` of indicative sequences for a given output symbol `z`. */
    MatrixXd f(const Sequences &Y, Symbol z, const Sequences &X) {
        if (nU_ == 0) return f(Y, Sequence(std::vector<Symbol>{z}, nO_, nU_), X);
        return MatrixXd();
    }

    /**
     * Return the matrix of estimates for \f$[ f( x z y ) ]_{y \in X, x \in X}\f$ with rows indexed by the given set `Y` of characteristic sequences and columns indexed by the given set `X` of indicative sequences for a given input-output symbol pair z = (`u`, `o`). In the case of an output-only system, the input `u` is simply ignored. */
    MatrixXd f(const Sequences &Y, Symbol o, Symbol u, const Sequences &X) {
        if (nU_ != 0) return f(Y, Sequence(std::vector<Symbol>{u, o}, nO_, nU_), X);
        else          return f(Y, Sequence(std::vector<Symbol>{o}, nO_, nU_), X);
    }

    /**
     * Return the matrix of estimates for \f$[ f( x s y ) ]_{y \in X, x \in X}\f$ with rows indexed by the given set `Y` of characteristic sequences and columns indexed by the given set `X` of indicative sequences for a given `Sequence` `s`. */
    MatrixXd f(const Sequences &Y, const Sequence s, const Sequences &X) {
        unsigned long rows = Y.size(), cols = X.size();
        MatrixXd F(rows, cols);
        State state_Xj(*this);
        for (unsigned long j = 0; j < cols; ++j) {
            state_Xj.reset(true) << X[j];
            for (unsigned long i = 0; i < rows; ++i) {
                state_ << state_Xj << s << Y[i];
                F.coeffRef(i, j) = state_.f();
            }
        }
        return F;
    }

    /**
     * Return a variance estimate for the estimate of f( `z` ) for the given output symbol `z`. */
    double v(Symbol z) throw(std::invalid_argument) {
        if (nU_ != 0) throw std::invalid_argument("input symbol required");
        return (state_.reset(true) << z).v();
    }

    /**
     * Return a variance estimate for the estimate of f( z ) for the given input-output symbol pair z = (`u`, `o`). In the case of an output-only system, the input `u` is simply ignored. */
    double v(Symbol o, Symbol u) { return (state_.reset(true) << std::make_pair(o,u)).v(); }

    /**
     * Return a variance estimate for the estimate of f( `sequence` ). */
    double v(const Sequence &sequence) { return (state_.reset(true) << sequence).v(); }

    /**
     * Return the matrix of element-wise variance estimates corresponding to the estimates for \f$[ f( x y ) ]_{y \in X, x \in X}\f$ with rows indexed by the given set `Y` of characteristic sequences and columns indexed by the given set `X` of indicative sequences. */
    MatrixXd v(const Sequences &Y, const Sequences &X) { return v(Y, Sequence(0, nO_, nU_), X); }

    /**
     * Return the matrix of element-wise variance estimates corresponding to the estimates for \f$[ f( x z y ) ]_{y \in X, x \in X}\f$ with rows indexed by the given set `Y` of characteristic sequences and columns indexed by the given set `X` of indicative sequences for a given output symbol `z`. */
    MatrixXd v(const Sequences &Y, Symbol z, const Sequences &X) {
        if (nU_ == 0) return v(Y, Sequence(std::vector<Symbol>{z}, nO_, nU_), X);
        return MatrixXd();
    }

    /**
     * Return the matrix of element-wise variance estimates corresponding to the estimates for \f$[ f( x z y ) ]_{y \in X, x \in X}\f$ with rows indexed by the given set `Y` of characteristic sequences and columns indexed by the given set `X` of indicative sequences for a given input-output symbol pair z = (`u`, `o`). In the case of an output-only system, the input `u` is simply ignored. */
    MatrixXd v(const Sequences &Y, Symbol o, Symbol u, const Sequences &X) {
        if (nU_ != 0) return v(Y, Sequence(std::vector<Symbol>{u, o}, nO_, nU_), X);
        else          return v(Y, Sequence(std::vector<Symbol>{o}, nO_, nU_), X);
    }

    /**
     * Return the matrix of element-wise variance estimates corresponding to the estimates for \f$[ f( x s y ) ]_{y \in X, x \in X}\f$ with rows indexed by the given set `Y` of characteristic sequences and columns indexed by the given set `X` of indicative sequences for a given `Sequence` `s`. */
    MatrixXd v(const Sequences &Y, const Sequence s, const Sequences &X) {
        MatrixXd F, V;
        fv(F, V, Y, s, X);
        return V;
    }

    SWIGCODE(%apply MatrixXd& OUTPUT { MatrixXd& F, MatrixXd& V };)
    SWIGCODE(%apply double& OUTPUT { double& f, double& v };)

    /**
     * Return
     * \if PY
     * in a tuple (`f`, `v`)
     * \else
     * (in the output arguments `f` and `v`)
     * \endif
     * an estimate `f` of f( `z` ) for the given output symbol `z` together with the corresponding variance estimate `v`. */
    C1(void) PY2(tuple<double, double>)
    fv(C3(double &f, double &v,) Symbol z) throw(std::invalid_argument) {
        if (nU_ != 0) throw std::invalid_argument("input symbol required");
        state_.reset(true) << z;
        f = state_.f(); v = state_.v();
    }

    /**
     * Return
     * \if PY
     * in a tuple (`f`, `v`)
     * \else
     * (in the output arguments `f` and `v`)
     * \endif
     * an estimate `f` of f( z ) for the given input-output symbol pair z = (`u`, `o`) together with the corresponding variance estimate `v`. In the case of an output-only system, the input `u` is simply ignored. */
    C1(void) PY2(tuple<double, double>)
    fv(C3(double &f, double &v,) Symbol o, Symbol u) {
        state_.reset(true) << std::make_pair(o,u);
        f = state_.f(); v = state_.v();
    }

    /**
     * Return
     * \if PY
     * in a tuple (`f`, `v`)
     * \else
     * (in the output arguments `f` and `v`)
     * \endif
     * an estimate of f( `sequence` ) together with the corresponding variance estimate `v`. */
    C1(void) PY2(tuple<double, double>)
    fv(C3(double &f, double &v,) const Sequence &sequence) {
        state_.reset(true) << sequence;
        f = state_.f(); v = state_.v();
    }

    /**
     * Return
     * \if PY
     * in a tuple (`F`, `V`)
     * \else
     * (in the output arguments `F` and `V`)
     * \endif
     * the matrix `F` of estimates for \f$[ f( x y ) ]_{y \in X, x \in X}\f$ with rows indexed by the given set `Y` of characteristic sequences and columns indexed by the given set `X` of indicative sequences, together with the corresponding matrix `V` of element-wise variance estimates for the estimates returned in `F`. */
    C1(void) PY2(tuple<MatrixXd, MatrixXd>)
    fv(C3(MatrixXd &F, MatrixXd &V,) const Sequences &Y, const Sequences &X) {
        fv(F, V, Y, Sequence(0, nO_, nU_), X);
    }

    /**
     * Return
     * \if PY
     * in a tuple (`F`, `V`)
     * \else
     * (in the output arguments `F` and `V`)
     * \endif
     * the matrix `F` of estimates for \f$[ f( x z y ) ]_{y \in X, x \in X}\f$ with rows indexed by the given set `Y` of characteristic sequences and columns indexed by the given set `X` of indicative sequences for a given output symbol `z`, together with the corresponding matrix `V` of element-wise variance estimates for the estimates returned in `F`. */
    C1(void) PY2(tuple<MatrixXd, MatrixXd>)
    fv(C3(MatrixXd &F, MatrixXd &V,) const Sequences &Y, Symbol z, const Sequences &X) throw(std::invalid_argument) {
        if (nU_ != 0) throw std::invalid_argument("input symbol required");
        fv(F, V, Y, Sequence(std::vector<Symbol>{z}, nO_, 0), X);
    }

    /**
     * Return
     * \if PY
     * in a tuple (`F`, `V`)
     * \else
     * (in the output arguments `F` and `V`)
     * \endif
     * the matrix `F` of estimates for \f$[ f( x z y ) ]_{y \in X, x \in X}\f$ with rows indexed by the given set `Y` of characteristic sequences and columns indexed by the given set `X` of indicative sequences for a given input-output symbol pair z = (`u`, `o`), together with the corresponding matrix `V` of element-wise variance estimates for the estimates returned in `F`. In the case of an output-only system, the input `u` is simply ignored. */
    C1(void) PY2(tuple<MatrixXd, MatrixXd>)
    fv(C3(MatrixXd &F, MatrixXd &V,) const Sequences &Y, Symbol o, Symbol u, const Sequences &X) {
        if (nU_ == 0) fv(F, V, Y, Sequence(std::vector<Symbol>{o}, nO_, 0), X);
        else          fv(F, V, Y, Sequence(std::vector<Symbol>{u, o}, nO_, nU_), X);
    }

    /**
     * Return
     * \if PY
     * in a tuple (`F`, `V`)
     * \else
     * (in the output arguments `F` and `V`)
     * \endif
     * the matrix `F` of estimates for \f$[ f( x s y ) ]_{y \in X, x \in X}\f$ with rows indexed by the given set `Y` of characteristic sequences and columns indexed by the given set `X` of indicative sequences for a given `Sequence` `s`, together with the corresponding matrix `V` of element-wise variance estimates for the estimates returned in `F`. */
    C1(void) PY2(tuple<MatrixXd, MatrixXd>)
    fv(C3(MatrixXd &F, MatrixXd &V,) const Sequences &Y, const Sequence s, const Sequences &X) {
        unsigned long rows = Y.size(), cols = X.size();
        F.resize(rows, cols); V.resize(rows, cols);
        State state_Xj(*this);
        for (unsigned long j = 0; j < cols; ++j) {
            state_Xj.reset(true) << X[j];
            for (unsigned long i = 0; i < rows; ++i) {
                state_ << state_Xj << s << Y[i];
                F.coeffRef(i, j) = state_.f();
                V.coeffRef(i, j) = state_.v();
            }
        }
    }

    SWIGCODE(%clear MatrixXd& F, MatrixXd& V, double& f, double& v;)
    //</editor-fold>

    //<editor-fold desc="Regularization parameters">
    SWIGCODE(%feature ("kwargs") regularization;)
    SWIGCODE(%apply double *OUTPUT { double *zConfidenceIntervalSizeOut, double *minimumVarianceOut };)
    SWIGCODE(%apply std::string *OUTPUT { std::string *confidenceIntervalTypeOut };)
    /**
     Set (optional) and then return the regularization parameters for the `Estimator`. This is done as follows:
     - First, if a `preset` ("none" / "default") is specified, all regularization parameters are set accordingly.
     - Next, any non-default argument causes the corresponding regularization parameter to be set to the given value, while any argument left at its default value (-1) has no effect.
     - Finally, the current regularization parameters are returned
     \if PY
     in a tuple in the same order as they appear as function arguments. This allows writing python code such as:
     \verbatim
     old_params = estimator.regularization()
     ...
     estimator.regularization(*old_params)
     \endverbatim
     \else
     in the corresponding output arguments `...Out` (if not NULL).
     \endif
     */
    C1(void) PY1(tuple)
    regularization(C4(double *zConfidenceIntervalSizeOut, std::string *confidenceIntervalTypeOut, double *minimumVarianceOut,)
                   double zConfidenceIntervalSize = -1,
                   std::string confidenceIntervalType = "",
                   double minimumVariance = -1,
                   std::string preset = "") throw(std::invalid_argument) {
        if (preset == "default") {
            z = 1;
            confidenceIntervalType_ = "Wilson";
            minimumVariance_         = 0;
        } else if (preset == "none") {
            z = 0;
            confidenceIntervalType_ = "Wilson";
            minimumVariance_         = 0;
        } else if (preset != "") {
            throw std::invalid_argument("unrecognized preset");
        }
        if (zConfidenceIntervalSize != -1) this->z = zConfidenceIntervalSize;
        if (confidenceIntervalType != "") this->confidenceIntervalType_ = confidenceIntervalType;
        if (minimumVariance         != -1) this->minimumVariance_ = minimumVariance;
        if (zConfidenceIntervalSizeOut) *zConfidenceIntervalSizeOut = this->z;
        if (confidenceIntervalTypeOut) *confidenceIntervalTypeOut = this->confidenceIntervalType_;
        if (minimumVarianceOut) *minimumVarianceOut = this->minimumVariance_;
    }

    SWIGCODE(%clear double *zConfidenceIntervalSizeOut, std::string *confidenceIntervalTypeOut, double *minimumVarianceOut;)

#ifndef SWIG
#ifndef PY
    /**
     * Set the regularization parameters for the `Estimator`. This is a convenience function that simply calls `regularization(NULL, NULL, NULL, zConfidenceIntervalSize, confidenceIntervalType, minimumVariance, preset);` */
    void regularization(double zConfidenceIntervalSize = -1,
                        std::string confidenceIntervalType = "",
                        double minimumVariance = -1,
                        std::string preset = "") throw(std::invalid_argument) {
        regularization(NULL, NULL, NULL, zConfidenceIntervalSize, confidenceIntervalType, minimumVariance, preset);
    }
    /**
    * Set the regularization parameters for the `Estimator` to the given `preset`. This is a convenience function that simply calls `regularization(NULL, NULL, NULL, -1, "", -1, preset);` */
    void regularization(std::string preset) throw(std::invalid_argument) {
        regularization(NULL, NULL, NULL, -1, "", -1, preset);
    }
#endif
#endif

    std::string confidenceIntervalType() const { return confidenceIntervalType_; }

    double zConfidenceIntervalSize() const { return z; }

    double minimumVariance() const { return minimumVariance_; }

    //</editor-fold>

private:
    int nO_;              ///< the size of the output alphabet
    int nU_;              ///< the size of the input alphabet
    long N_;            ///< the length of the sample sequence from which the estimates are calculated

    std::string confidenceIntervalType_;
    double z;
    double minimumVariance_;

    SWIGCODE(%ignore State::operator=;)
    /**
     * Estimates for a sequence \f$x\f$ are computed by parsing the sequence from left to right, while gathering the required statistics (occurrence counts in the underlying sample sequence) by traversing the suffix tree accordingly.
     *
     * A `State` object captures the relevant information during the parsing of sequence \f$x\f$. The estimates can then be accessed via `f()` and `v()`.
     *
     * Therefore, typically do:
     *
     * > `state.reset(estimateVariance) << sequence << symbol << symbol << sequence;`
     * > `f = state.f(); v = state.v()
     *
     */
    class State {
        friend class Estimator;
        State(const Estimator& estimator) : estimator_(estimator), pos_(estimator.stree_) { reset(true); }

        State& reset(bool estimateVariance = true) {
            pos_.setRoot();
            f_ = f2_ = 1;
            v_ = 0;
            k_ = 0;
            estimateVariance_ = estimateVariance;
            return *this;
        }

        State& operator <<(const State& state) {
            pos_.set(state.pos_);
            f_ = state.f_;
            f2_ = state.f2_;
            v_ = state.v_;
            k_ = state.k_;
            estimateVariance_ = state.estimateVariance_;
            return *this;
        }

        State& operator <<(Symbol o) { return operator<< (std::make_pair(o, 0)); }

        State& operator <<(std::pair<Symbol, Symbol> ou) {
            k_++;
            /* `n` is the number of possible occurrences for `x_k`, and `c` is the number of occurrences of `x_k`. */
            if (estimator_.nU_ != 0) { pos_.toSymbol(ou.second); }
            double n = pos_.count();
            if (pos_.isSuffix()) { --n; }
            pos_.toSymbol(ou.first);
            double c = pos_.count();
            double p = (n == 0 ? 1.0 / estimator_.nO_ : c / n);
            f_ *= p;

            if (not estimateVariance_) { return *this; }

            /* Next we compute a confidence interval for p: */
            double p_mid = (n == 0 ? 0.5 : c / n);
            double ci_lower = 0.0, ci_upper = 0.0;
            if (estimator_.z != 0) {
                double z2 = estimator_.z * estimator_.z;
                ci_lower = ci_upper = 1.0;
                if (n > 0) {
                    p_mid = (c + 0.5 * z2) / (n + z2);
                    if (estimator_.confidenceIntervalType_ == "Agresti–Coull") {
                        ci_lower = ci_upper = estimator_.z * std::sqrt(p_mid * (1 - p_mid) / (n + z2));
                    } else if (estimator_.confidenceIntervalType_ == "Wilson") {
                        ci_lower = ci_upper = estimator_.z * std::sqrt(n * p * (1 - p) + z2 / 4) / (n + z2);
                    } else if (estimator_.confidenceIntervalType_ == "Wilson_CC") { // Wilson score interval with continuity correction (more conservative):
                        if (c > 0) ci_lower = (0.5 + estimator_.z * std::sqrt(n * p * (1 - p) + z2 / 4 - 0.25 / n + p - 0.5)) / (n + z2);
                        if (c < n) ci_upper = (0.5 + estimator_.z * std::sqrt(n * p * (1 - p) + z2 / 4 - 0.25 / n - p + 0.5)) / (n + z2);
                    }
                }
            }
            double p_lower = std::max(p_mid - ci_lower, 0.0);
            double p_upper = std::min(p_mid + ci_upper, 1.0);
            double p_centered = (p_mid < 0.5 ? std::min(p_upper, 0.5) : std::max(p_lower, 0.5));
            double p_extreme = std::min(p_lower, 1 - p_upper);

            double E_p2_overestimate = p_upper * p_upper;
            double var_p_overestimate = 0.5;
            double var_p_underestimate = 0.0;
            if (n > 0) {
                var_p_overestimate = p_centered * (1 - p_centered) / n;
                var_p_underestimate = p_extreme * (1 - p_extreme) / n;
            }

            v_ = v_ * (E_p2_overestimate - var_p_underestimate) + f2_ * var_p_overestimate;
            f2_ *= E_p2_overestimate;
            return *this;
        }

        State& operator <<(const Sequence& sequence) {
            for (long i = 0; i < sequence.length(); ++i) { operator<< (std::make_pair(sequence.o(i), sequence.u(i))); }
            return *this;
        }

        double f() const { return f_; }

        double v() const {
            assert(estimateVariance_);
            double var = v_;
            if (k_ == 0) { var = 1e-15; }
            return var;
        }

        const Estimator& estimator_; ///< the `Estimator` that this `State` belongs to
        stree::Position pos_;        ///< the position in the suffix tree for the currently estimated sequence.
        double f_;               ///< the current estimate
        double f2_;
        double v_;
        long k_;                 ///< the length of the currently parsed sequence
        bool estimateVariance_;
    };

    const std::shared_ptr<stree::STree> stree_; ///< the suffix tree for the underlying sample sequence
    State state_;                   ///< captures the relevant information during the parsing of a sequence
}; // class Estimator

} // namespace tom
