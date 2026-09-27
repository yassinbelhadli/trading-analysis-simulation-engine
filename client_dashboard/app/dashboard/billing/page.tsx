"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getPaymentHistory,
  getReceipts,
  getPaymentMethodLabel,
  getMySubscription,
  getClientSettings,
  getProviderStatus,
  listAvailablePlans,
  createCheckout,
  getCheckoutStatus,
  getPaymentMethods,
  submitManualPayment,
  uploadPaymentProof,
  clientValidateCoupon,
  type PaymentInfo,
  type ReceiptInfo,
  type AvailablePlan,
  type CheckoutSession,
  type PaymentMethod,
  type ProviderStatus,
  type ClientSubscriptionResponse,
  type ClientFieldDef,
} from "@/lib/api";
import { PageHeader, Card, EmptyState, Table, Td, Badge, Skeleton, Button } from "@ds/components/ui";
import { Modal } from "@ds/components/Modal";
import { formatPrice, getPlanPrice } from "@/lib/currency";
import { parseApiError } from "@/lib/errors";
import { formatUserDateTime } from "@/lib/timezone";
import { useLocale } from "@/components/LocaleContext";

type CheckoutStep =
  | "plan"
  | "coupon"
  | "payment_method"
  | "review"
  | "payment"
  | "processing"
  | "waiting"
  | "success"
  | "failed";

export default function BillingPage() {
  // Data
  const [payments, setPayments] = useState<PaymentInfo[]>([]);
  const [receipts, setReceipts] = useState<ReceiptInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Subscription + plans
  const [subData, setSubData] = useState<ClientSubscriptionResponse | null>(null);
  const [availablePlans, setAvailablePlans] = useState<AvailablePlan[]>([]);
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null);

  // Global locale (currency/timezone come from the top-bar selectors)
  const { t, currency: localeCurrency, timezone: userTimezone } = useLocale();

  // Checkout flow state
  const [checkoutStep, setCheckoutStep] = useState<CheckoutStep>("plan");
  const [selectedPlan, setSelectedPlan] = useState<AvailablePlan | null>(null);
  const [selectedCurrency, setSelectedCurrency] = useState("MAD");
  const [couponCode, setCouponCode] = useState("");
  const [couponResult, setCouponResult] = useState<{
    valid: boolean;
    original_price: number;
    discount_amount: number;
    final_price: number;
    message: string;
  } | null>(null);
  const [couponLoading, setCouponLoading] = useState(false);
  const [checkoutSession, setCheckoutSession] = useState<CheckoutSession | null>(null);
  const [checkoutError, setCheckoutError] = useState("");

  // Payment method state
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<string>("stripe");
  const [availableMethods, setAvailableMethods] = useState<PaymentMethod[]>([]);
  const [methodsLoading, setMethodsLoading] = useState(false);

  // Manual payment state — configuration-driven: values for the owner-defined
  // client fields are stored generically (keyed by the field's "key").
  const [clientFieldValues, setClientFieldValues] = useState<Record<string, string>>({});
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [proofUrl, setProofUrl] = useState("");
  const [proofUploading, setProofUploading] = useState(false);
  const [proofError, setProofError] = useState("");
  const [submittingManual, setSubmittingManual] = useState(false);

  // Crypto expiry countdown
  const [timeLeft, setTimeLeft] = useState<string>("");

  // Notification
  const [notif, setNotif] = useState<{ ok: boolean; text: string } | null>(null);

  // Receipt detail modal
  const [viewingReceipt, setViewingReceipt] = useState<ReceiptInfo | null>(null);

  const loadBase = useCallback(async () => {
    try {
      const [payResult, recResult, subResult, settingsResult, providerResult, plansResult] = await Promise.all([
        getPaymentHistory(50).catch(() => ({ payments: [], total: 0 })),
        getReceipts(50).catch(() => ({ receipts: [] })),
        getMySubscription().catch(() => null),
        getClientSettings().catch(() => ({ billing_currency: "USD" })),
        getProviderStatus().catch(() => ({ configured: false, provider: "none" })),
        listAvailablePlans().catch(() => ({ plans: [] })),
      ]);
      setPayments(payResult.payments || []);
      setReceipts(recResult.receipts || []);
      setSubData(subResult);
      setProviderStatus(providerResult);
      setAvailablePlans(plansResult.plans || []);
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBase();

    // Check URL params for payment result
    const params = new URLSearchParams(window.location.search);
    const paymentStatus = params.get("payment");
    const paymentId = params.get("payment_id");
    if (paymentStatus === "success" && paymentId) {
      // Reconstruct a minimal checkout session so the polling effect can
      // resolve the payment status after the provider redirect. Without this,
      // the page would stay stuck on "Processing" forever because
      // checkoutSession (and thus payment_id) was never set.
      setCheckoutSession({ payment_id: paymentId } as CheckoutSession);
      setCheckoutStep("processing");
      window.history.replaceState({}, "", "/dashboard/billing");
    } else if (paymentStatus === "cancelled") {
      setNotif({ ok: false, text: t("billing.paymentCancelled") });
      window.history.replaceState({}, "", "/dashboard/billing");
    }
  }, [loadBase]);

  // Keep checkout currency in sync with the global currency selector
  useEffect(() => {
    setSelectedCurrency(localeCurrency);
    setCouponResult(null);
  }, [localeCurrency]);

  // Fetch payment methods when step changes
  useEffect(() => {
    if (checkoutStep !== "payment_method") return;
    setMethodsLoading(true);
    getPaymentMethods(selectedCurrency)
      .then((res) => {
        setAvailableMethods(res.methods || []);
        const firstConfigured = res.methods?.find((m) => m.is_configured);
        if (firstConfigured) setSelectedPaymentMethod(firstConfigured.name);
      })
      .catch(() => setAvailableMethods([]))
      .finally(() => setMethodsLoading(false));
  }, [checkoutStep, selectedCurrency]);

  // Poll payment status when in processing step
  useEffect(() => {
    if (checkoutStep !== "processing" || !checkoutSession?.payment_id) return;

    const poll = async () => {
      try {
        const result = await getCheckoutStatus(checkoutSession.payment_id);
        if (result.payment.status === "PAID") {
          setCheckoutStep("success");
          loadBase();
        } else if (result.payment.status === "FAILED" || result.payment.status === "CANCELLED") {
          setCheckoutStep("failed");
          setCheckoutError(result.payment.failure_reason || t("billing.paymentNotCompletedText"));
        } else if (result.payment.status === "PENDING_VERIFICATION" || result.payment.status === "SUBMITTED") {
          // Manual payment awaiting owner review — stop polling, show waiting state.
          setCheckoutStep("waiting");
        }
      } catch { /* continue polling */ }
    };

    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, [checkoutStep, checkoutSession?.payment_id, loadBase]);

  // Crypto expiry countdown timer
  useEffect(() => {
    if (!checkoutSession?.expired_at) {
      setTimeLeft("");
      return;
    }
    const updateTimer = () => {
      const now = new Date().getTime();
      const expiry = new Date(checkoutSession.expired_at!).getTime();
      const diff = expiry - now;
      if (diff <= 0) {
        setTimeLeft("Expired");
        return false;
      }
      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setTimeLeft(`${mins}:${secs.toString().padStart(2, "0")}`);
      return true;
    };
    if (!updateTimer()) return;
    const timer = setInterval(() => {
      if (!updateTimer()) clearInterval(timer);
    }, 1000);
    return () => clearInterval(timer);
  }, [checkoutSession?.expired_at]);

  // ---- Checkout handlers ----

  const handleSelectPlan = (plan: AvailablePlan) => {
    setSelectedPlan(plan);
    setSelectedCurrency(localeCurrency);
    setCouponCode("");
    setCouponResult(null);
    setSelectedPaymentMethod("stripe");
    setCheckoutStep("coupon");
  };

  const handleApplyCoupon = async () => {
    if (!couponCode.trim() || !selectedPlan) return;
    setCouponLoading(true);
    setCouponResult(null);
    try {
      const result = await clientValidateCoupon({
        code: couponCode.trim(),
        plan_id: selectedPlan.id,
        currency: selectedCurrency,
      });
      setCouponResult(result);
    } catch (err) {
      setCouponResult({
        valid: false,
        original_price: 0,
        discount_amount: 0,
        final_price: 0,
        message: err instanceof Error ? err.message : t("billing.invalidCoupon"),
      });
    } finally {
      setCouponLoading(false);
    }
  };

  const handleProceedToPayment = async () => {
    if (!selectedPlan) return;
    setCheckoutError("");
    setCheckoutStep("payment");

    try {
      // Crypto methods price in their own ticker (BTC/ETH/SOL/USDT), not MAD/USD/EUR.
      const isCryptoMethod = selectedMethodInfo?.category === "crypto";
      const checkoutCurrency = isCryptoMethod && selectedMethodInfo?.ticker
        ? selectedMethodInfo.ticker
        : selectedCurrency;
      const result = await createCheckout({
        plan_id: selectedPlan.id,
        currency: checkoutCurrency,
        coupon_code: couponResult?.valid ? couponCode.trim() : undefined,
        payment_method: selectedPaymentMethod,
      });

      setCheckoutSession(result.checkout);

      const isManual = result.checkout.payment_method_type === "manual" || result.checkout.payment_method_type === "manual_crypto";

      if (isManual) {
        setCheckoutStep("payment");
      } else if (result.checkout.checkout_url) {
        window.location.href = result.checkout.checkout_url;
      } else {
        setCheckoutStep("failed");
        setCheckoutError(t("billing.providerNotConfigured"));
      }
    } catch (err) {
      setCheckoutStep("failed");
      setCheckoutError(parseApiError(err));
    }
  };

  const handleSubmitManualPayment = async () => {
    if (!checkoutSession?.payment_id) return;
    const cfg = checkoutSession.owner_config;
    const fields = cfg?.client_fields || [];
    // Frontend validation: proof file is mandatory for manual methods
    if (cfg?.receipt_required !== false && !proofUrl) {
      setProofError(t("checkout.proofRequired"));
      return;
    }
    // Frontend validation: required fields marked with * must be present
    const missing = fields.filter((f) => f.required && !(clientFieldValues[f.key] || "").trim());
    if (missing.length > 0) {
      setProofError(t("checkout.requiredFieldsMissing"));
      return;
    }
    setSubmittingManual(true);
    try {
      // Build the dynamic payload from the owner-defined field definitions.
      const client_fields_data: Record<string, unknown> = {};
      for (const f of fields) {
        const raw = (clientFieldValues[f.key] || "").trim();
        if (!raw) continue;
        if (f.type === "number") client_fields_data[f.key] = Number(raw);
        else if (f.type === "date" || f.type === "datetime") client_fields_data[f.key] = new Date(raw).toISOString();
        else client_fields_data[f.key] = raw;
      }
      await submitManualPayment(checkoutSession.payment_id, {
        manual_reference: clientFieldValues["payment_reference"] || undefined,
        manual_proof_url: proofUrl || undefined,
        payer_name: clientFieldValues["payer_name"] || undefined,
        payer_phone: clientFieldValues["payer_phone"] || undefined,
        payment_date: clientFieldValues["payment_date"]
          ? new Date(clientFieldValues["payment_date"]).toISOString()
          : undefined,
        amount_paid: clientFieldValues["amount_paid"]
          ? parseFloat(clientFieldValues["amount_paid"])
          : undefined,
        client_fields_data,
      });
      setCheckoutStep("processing");
      setNotif({ ok: true, text: t("checkout.submittedForVerification") });
    } catch (err) {
      setNotif({ ok: false, text: parseApiError(err) });
    } finally {
      setSubmittingManual(false);
    }
  };

  const handleProofFileChange = async (file: File | null) => {
    setProofError("");
    setProofFile(file);
    setProofUrl("");
    if (!file) return;
    // Frontend validation: type + size
    const ext = file.name.split(".").pop()?.toLowerCase() || "";
    const allowed = ["jpg", "jpeg", "png", "pdf"];
    if (!allowed.includes(ext)) {
      setProofError(t("checkout.unsupportedType"));
      setProofFile(null);
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setProofError(t("checkout.fileTooLarge"));
      setProofFile(null);
      return;
    }
    if (!checkoutSession?.payment_id) return;
    setProofUploading(true);
    try {
      const res = await uploadPaymentProof(checkoutSession.payment_id, file);
      setProofUrl(res.url);
    } catch (err) {
      setProofError(parseApiError(err));
      setProofFile(null);
    } finally {
      setProofUploading(false);
    }
  };

  const resetCheckout = () => {
    setCheckoutStep("plan");
    setSelectedPlan(null);
    setCouponCode("");
    setCouponResult(null);
    setCheckoutSession(null);
    setCheckoutError("");
    setSelectedPaymentMethod("stripe");
    setClientFieldValues({});
    setProofFile(null);
    setProofUrl("");
    setProofError("");
  };

  // ---- Derived ----

  const sub = subData?.subscription;
  const originalPrice = selectedPlan ? getPlanPrice(selectedPlan, selectedCurrency) : null;
  const finalPrice = couponResult?.valid ? couponResult.final_price : originalPrice;
  const discountAmount = couponResult?.valid ? couponResult.discount_amount : 0;

  const selectedMethodInfo = availableMethods.find((m) => m.name === selectedPaymentMethod);
  const isManualMethod = selectedMethodInfo?.is_manual || false;

  if (loading) {
    return (
      <div className="max-w-4xl flex flex-col gap-5">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl flex flex-col gap-5">
      <PageHeader title={t("billing.title")} subtitle={t("billing.subtitle")} />

      {error && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 p-3 text-sm text-danger">
          {error}
        </div>
      )}

      {notif && (
        <div className={`rounded-lg border p-3 text-sm ${
          notif.ok
            ? "border-ok/30 bg-ok/5 text-ok"
            : "border-danger/30 bg-danger/5 text-danger"
        }`}>
          {notif.text}
        </div>
      )}

      {/* ===== PLAN CARDS ===== */}
      {checkoutStep === "plan" && availablePlans.length > 0 && (
        <Card title={t("billing.availablePlans")} icon="tag">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {availablePlans.map((p) => (
              <PlanCard
                key={p.id}
                plan={p}
                currency={localeCurrency}
                current={sub?.plan === p.id}
                onSelect={() => handleSelectPlan(p)}
              />
            ))}
          </div>
        </Card>
      )}

      {/* ===== CHECKOUT WIZARD (when not on plan step) ===== */}

      {/* Step 2: Coupon (optional) */}
      {checkoutStep === "coupon" && selectedPlan && (
        <Card title={t("billing.couponCode")} icon="tag">
          <div className="flex flex-col gap-4">
            <p className="text-sm text-ink-soft">{t("billing.enterCoupon")}</p>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={couponCode}
                onChange={(e) => { setCouponCode(e.target.value.toUpperCase()); setCouponResult(null); }}
                placeholder={t("billing.couponPlaceholder")}
                className="h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink w-48 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
              />
              <Button
                variant="secondary"
                size="sm"
                onClick={handleApplyCoupon}
                disabled={!couponCode.trim() || couponLoading}
                loading={couponLoading}
              >
                {t("billing.apply")}
              </Button>
            </div>
            {couponResult?.valid && <div className="text-sm text-ok">{couponResult.message}</div>}
            {couponResult && !couponResult.valid && <div className="text-sm text-danger">{couponResult.message}</div>}
            <div className="flex gap-2">
              <Button variant="ghost" onClick={resetCheckout}>{t("billing.backToPlans")}</Button>
              <Button onClick={() => setCheckoutStep("payment_method")}>{t("billing.continue")}</Button>
            </div>
          </div>
        </Card>
      )}

      {/* Step 3: Payment Method */}
      {checkoutStep === "payment_method" && selectedPlan && (
        <Card title={t("checkout.selectMethod")} icon="credit-card">
          <div className="flex flex-col gap-4">
            <p className="text-sm text-ink-soft">
              {t("checkout.chooseHowToPay", { plan: selectedPlan.name, currency: selectedCurrency })}
            </p>

            {methodsLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : availableMethods.length === 0 ? (
              <div className="rounded-lg border border-warn/30 bg-warn/5 p-3 text-sm text-warn">
                {t("checkout.noMethods", { currency: selectedCurrency })}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {availableMethods.map((m) => (
                  <button
                    key={m.name}
                    type="button"
                    onClick={() => setSelectedPaymentMethod(m.name)}
                    disabled={!m.is_configured && !m.is_manual}
                    className={`flex flex-col items-start gap-1 px-4 py-3 rounded-lg border text-sm text-left transition-colors ${
                      selectedPaymentMethod === m.name
                        ? "border-brand-500 bg-brand-tint text-brand-400"
                        : m.is_configured || m.is_manual
                          ? "border-line text-ink hover:border-line-strong"
                          : "border-line text-ink-muted opacity-50 cursor-not-allowed"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{m.display_name}</span>
                      {m.is_manual && <Badge tone="amber">{t("checkout.manual")}</Badge>}
                      {!m.is_configured && !m.is_manual && <Badge tone="gray">{t("checkout.notAvailable")}</Badge>}
                    </div>
                    <span className="text-xs text-ink-muted">{m.description}</span>
                  </button>
                ))}
              </div>
            )}

            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setCheckoutStep("coupon")}>{t("common.back")}</Button>
              <Button
                onClick={() => setCheckoutStep("review")}
                disabled={!selectedPaymentMethod || (!selectedMethodInfo?.is_configured && !selectedMethodInfo?.is_manual)}
              >
                {t("checkout.continueToReview")}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Step 5: Order Review */}
      {checkoutStep === "review" && selectedPlan && (
        <Card title={t("checkout.orderReview")} icon="info">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2 text-sm">
              <ReviewRow k={t("billing.plan")} v={selectedPlan.name} strong />
              <ReviewRow k={t("billing.duration")} v={selectedPlan.duration_days ? t("billing.days", { n: selectedPlan.duration_days }) : "—"} />
              <ReviewRow k={t("billing.currency")} v={selectedCurrency} />
              {couponResult?.valid && <ReviewRow k={t("billing.coupon")} v={couponCode} />}
              <ReviewRow
                k={t("billing.paymentMethod")}
                v={selectedMethodInfo?.display_name || selectedPaymentMethod}
              />
            </div>

            <div className="border-t border-line pt-3 flex flex-col gap-1.5 text-sm">
              <ReviewRow k={t("checkout.original")} v={formatPrice(originalPrice, selectedCurrency)} />
              {discountAmount > 0 && (
                <ReviewRow k={t("checkout.discount")} v={`-${formatPrice(discountAmount, selectedCurrency)}`} warn />
              )}
              <div className="border-t border-line pt-1.5">
                <ReviewRow k={t("checkout.amountToPay")} v={formatPrice(finalPrice, selectedCurrency)} strong />
              </div>
            </div>

            {!selectedMethodInfo?.is_configured && !selectedMethodInfo?.is_manual && (
              <div className="rounded-lg border border-warn/30 bg-warn/5 p-3 text-sm text-warn">
                {t("billing.providerNotConfigured")}
              </div>
            )}

            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setCheckoutStep("payment_method")}>{t("common.back")}</Button>
              <Button
                onClick={handleProceedToPayment}
                disabled={!selectedMethodInfo?.is_configured && !selectedMethodInfo?.is_manual}
              >
                {isManualMethod ? t("checkout.generateInstructions") : t("checkout.payNow")}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Step 6: Payment — configuration-driven rendering */}
      {checkoutStep === "payment" && checkoutSession && (
        <>
          {(checkoutSession.payment_method_type === "manual" || checkoutSession.payment_method_type === "manual_crypto") && (
            <DynamicPaymentInstructions
              session={checkoutSession}
              methodName={selectedMethodInfo?.display_name || t("checkout.manualPayment")}
              timeLeft={timeLeft}
              fieldValues={clientFieldValues}
              setFieldValues={setClientFieldValues}
              proofFile={proofFile}
              setProofFile={setProofFile}
              proofUrl={proofUrl}
              proofUploading={proofUploading}
              proofError={proofError}
              onProofFileChange={handleProofFileChange}
              submittingManual={submittingManual}
              onSubmit={handleSubmitManualPayment}
              onBack={() => setCheckoutStep("review")}
            />
          )}

          {checkoutSession.payment_method_type === "automatic" && (
            <Card title={t("checkout.redirectingTitle")} icon="credit-card">
              <div className="flex flex-col items-center gap-4 py-8">
                <div className="h-8 w-8 rounded-full bg-brand-tint flex items-center justify-center animate-pulse">
                  <span className="text-brand-400">&#8987;</span>
                </div>
                <p className="text-sm text-ink-soft">{t("checkout.redirectingText")}</p>
                <p className="text-xs text-ink-muted">{t("checkout.doNotClose")}</p>
                <p className="text-xs text-ink-muted">{t("checkout.paymentNum", { num: checkoutSession.payment_number })}</p>
              </div>
            </Card>
          )}

          {!checkoutSession.payment_method_type && isManualMethod && (
            <DynamicPaymentInstructions
              session={checkoutSession}
              methodName={selectedMethodInfo?.display_name || t("checkout.manualPayment")}
              timeLeft={timeLeft}
              fieldValues={clientFieldValues}
              setFieldValues={setClientFieldValues}
              proofFile={proofFile}
              setProofFile={setProofFile}
              proofUrl={proofUrl}
              proofUploading={proofUploading}
              proofError={proofError}
              onProofFileChange={handleProofFileChange}
              submittingManual={submittingManual}
              onSubmit={handleSubmitManualPayment}
              onBack={() => setCheckoutStep("review")}
            />
          )}
        </>
      )}

      {/* Step 7: Processing */}
      {checkoutStep === "processing" && (
        <Card title={t("checkout.processingTitle")} icon="credit-card">
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="h-8 w-8 rounded-full bg-brand-tint flex items-center justify-center animate-pulse">
              <span className="text-brand-400">&#8987;</span>
            </div>
            <p className="text-sm text-ink-soft">
              {isManualMethod
                ? t("checkout.waitingVerification")
                : t("checkout.waitingConfirmation")}
            </p>
            <p className="text-xs text-ink-muted">
              {isManualMethod
                ? t("checkout.teamWillReview")
                : t("checkout.fewMoments")}
            </p>
            {checkoutSession && (
              <p className="text-xs text-ink-muted">{t("checkout.paymentNum", { num: checkoutSession.payment_number })}</p>
            )}
          </div>
        </Card>
      )}

      {/* Step 7b: Waiting for manual verification (polling stopped) */}
      {checkoutStep === "waiting" && (
        <Card title={t("checkout.paymentSubmitted")} icon="clock">
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="h-8 w-8 rounded-full bg-brand-tint flex items-center justify-center">
              <span className="text-brand-400">&#8987;</span>
            </div>
            <p className="text-sm text-ink-soft">{t("checkout.waitingVerification")}</p>
            <p className="text-xs text-ink-muted">
              {t("checkout.teamWillReview")}
            </p>
            {checkoutSession && (
              <p className="text-xs text-ink-muted">{t("checkout.paymentNum", { num: checkoutSession.payment_number })}</p>
            )}
            <Button onClick={resetCheckout}>{t("billing.backToPlans")}</Button>
          </div>
        </Card>
      )}

      {/* Step 8: Success */}
      {checkoutStep === "success" && (
        <Card title={t("checkout.paymentSuccessful")} icon="check-circle">
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="h-12 w-12 rounded-full bg-ok/10 flex items-center justify-center">
              <span className="text-ok text-xl">&#10003;</span>
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-ink">{t("checkout.paymentConfirmed")}</p>
              <p className="text-sm text-ink-muted mt-1">{t("checkout.subscriptionActive")}</p>
              {checkoutSession && (
                <p className="text-xs text-ink-muted mt-2">{t("checkout.receiptNum", { num: checkoutSession.payment_number })}</p>
              )}
            </div>
            <div className="flex gap-2">
              <Button onClick={resetCheckout}>{t("billing.viewPlans")}</Button>
              <Button variant="secondary" onClick={() => { loadBase(); resetCheckout(); }}>
                {t("billing.refresh")}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Failed */}
      {checkoutStep === "failed" && (
        <Card title={t("checkout.paymentFailed")} icon="alert-triangle">
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="h-12 w-12 rounded-full bg-danger/10 flex items-center justify-center">
              <span className="text-danger text-xl">&#10007;</span>
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-ink">{t("checkout.paymentNotCompleted")}</p>
              {checkoutError && (
                <p className="text-sm text-danger mt-1">{checkoutError}</p>
              )}
            </div>
            <Button onClick={resetCheckout}>{t("billing.tryAgain")}</Button>
          </div>
        </Card>
      )}

      {/* Payment History */}
      <Card title={t("billing.paymentHistory")} icon="credit-card">
        {payments.length === 0 ? (
          <EmptyState
            icon="credit-card"
            title={t("billing.noPayments")}
            description={t("billing.noPaymentsDesc")}
          />
        ) : (
          <Table columns={[
            t("billing.colDate"),
            t("billing.colPaymentNum"),
            t("billing.colPlan"),
            t("billing.colAmount"),
            t("billing.colDiscount"),
            t("billing.colMethod"),
            t("billing.colStatus"),
          ]}>
            {payments.map((p) => (
              <tr key={p.id}>
                <Td className="text-ink-muted whitespace-nowrap">
                  {p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}
                </Td>
                <Td className="text-ink-soft font-mono text-xs">{p.payment_number}</Td>
                <Td className="text-ink-soft">{p.plan_name || p.plan_id}</Td>
                <Td mono className="text-right font-medium">{formatPrice(p.final_amount, p.currency)}</Td>
                <Td mono className="text-right text-ink-muted">
                  {p.discount_amount > 0 ? `-${formatPrice(p.discount_amount, p.currency)}` : "—"}
                </Td>
                <Td className="text-ink-soft">{getPaymentMethodLabel(p.payment_method || p.payment_provider)}</Td>
                <Td>
                  <Badge tone={
                    p.status === "PAID" ? "green" :
                    p.status === "PENDING" || p.status === "PENDING_VERIFICATION" || p.status === "AWAITING_PAYMENT" ? "amber" :
                    p.status === "FAILED" || p.status === "REJECTED" || p.status === "EXPIRED" ? "red" :
                    p.status === "REFUNDED" ? "amber" :
                    "gray"
                  }>
                    {p.status}
                  </Badge>
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {/* Receipts */}
      <Card title={t("receipt.title")} icon="receipt">
        {receipts.length === 0 ? (
          <EmptyState
            icon="receipt"
            title={t("receipt.noReceipts")}
            description={t("receipt.noReceiptsDesc")}
          />
        ) : (
          <Table columns={[
            t("receipt.colDate"),
            t("receipt.colReceiptNum"),
            t("receipt.colPlan"),
            t("receipt.colAmount"),
            t("receipt.colStatus"),
            t("receipt.colActions"),
          ]}>
            {receipts.map((r) => (
              <tr key={r.id}>
                <Td className="text-ink-muted whitespace-nowrap">
                  {r.paid_at ? new Date(r.paid_at).toLocaleDateString() : "—"}
                </Td>
                <Td className="text-ink-soft font-mono text-xs">{r.receipt_number}</Td>
                <Td className="text-ink-soft">{r.plan_name}</Td>
                <Td mono className="text-right font-medium">{formatPrice(r.final_amount, r.currency)}</Td>
                <Td>
                  <Badge tone="green">{r.payment_status}</Badge>
                </Td>
                <Td>
                  <div className="flex gap-1">
                    <Button size="sm" variant="ghost" icon="eye" onClick={() => setViewingReceipt(r)}>
                      {t("receipt.view")}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      icon="download"
                      onClick={() => setViewingReceipt(r)}
                    >
                      {t("receipt.print")}
                    </Button>
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {/* Receipt Detail Modal */}
      <Modal
        open={!!viewingReceipt}
        onClose={() => setViewingReceipt(null)}
        title={t("receipt.modalTitle", { num: viewingReceipt?.receipt_number || "" })}
        icon="info"
        size="lg"
        footer={
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setViewingReceipt(null)}>{t("common.close")}</Button>
            <Button
              icon="download"
              onClick={() => {
                const printContent = document.getElementById("receipt-print-area");
                if (!printContent) return;
                const win = window.open("", "_blank");
                if (!win) return;
                win.document.write(`
                  <html><head><title>${t("receipt.header", { num: viewingReceipt?.receipt_number || "" })}</title>
                  <style>
                    body { font-family: monospace; padding: 24px; color: #111; }
                    h1 { font-size: 18px; margin-bottom: 4px; }
                    .muted { color: #666; font-size: 12px; }
                    table { width: 100%; border-collapse: collapse; margin-top: 16px; }
                    td { padding: 6px 0; font-size: 13px; }
                    .label { color: #666; }
                    .total { font-weight: bold; border-top: 1px solid #ccc; }
                  </style></head><body>${printContent.innerHTML}</body></html>
                `);
                win.document.close();
                win.print();
              }}
            >
              {t("receipt.print")}
            </Button>
          </div>
        }
      >
        {viewingReceipt && (
          <div id="receipt-print-area" className="space-y-4 text-sm">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-ink">{t("receipt.header", { num: viewingReceipt.receipt_number })}</h3>
                <p className="text-xs text-ink-muted">{t("receipt.paymentHash", { id: viewingReceipt.payment_id?.slice(0, 8) })}</p>
              </div>
              <Badge tone="green">{viewingReceipt.payment_status}</Badge>
            </div>

            <div className="border-t border-line pt-3 space-y-2">
              <div className="flex justify-between">
                <span className="text-ink-soft">{t("billing.plan")}</span>
                <span className="text-ink font-medium">{viewingReceipt.plan_name}</span>
              </div>
              {viewingReceipt.plan_duration_days && (
                <div className="flex justify-between">
                  <span className="text-ink-soft">{t("billing.duration")}</span>
                  <span className="text-ink">{t("billing.days", { n: viewingReceipt.plan_duration_days })}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-ink-soft">{t("receipt.originalAmount")}</span>
                <span className="text-ink">{formatPrice(viewingReceipt.original_amount, viewingReceipt.currency)}</span>
              </div>
              {viewingReceipt.discount_amount > 0 && (
                <div className="flex justify-between">
                  <span className="text-ink-soft">{t("receipt.discount")}</span>
                  <span className="text-ok">-{formatPrice(viewingReceipt.discount_amount, viewingReceipt.currency)}</span>
                </div>
              )}
              {viewingReceipt.coupon_code && (
                <div className="flex justify-between">
                  <span className="text-ink-soft">{t("billing.coupon")}</span>
                  <span className="text-ink font-mono text-xs">{viewingReceipt.coupon_code}</span>
                </div>
              )}
              <div className="flex justify-between border-t border-line pt-2">
                <span className="text-ink font-semibold">{t("receipt.finalAmount")}</span>
                <span className="text-ink font-semibold">{formatPrice(viewingReceipt.final_amount, viewingReceipt.currency)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-soft">{t("billing.currency")}</span>
                <span className="text-ink">{viewingReceipt.currency}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-soft">{t("billing.paymentMethod")}</span>
                <span className="text-ink">{getPaymentMethodLabel(viewingReceipt.payment_method)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-soft">{t("receipt.paidDate")}</span>
                <span className="text-ink">
                  {viewingReceipt.paid_at
                    ? formatUserDateTime(viewingReceipt.paid_at, userTimezone)
                    : "—"}
                </span>
              </div>
              {viewingReceipt.subscription_start && (
                <div className="flex justify-between">
                  <span className="text-ink-soft">{t("receipt.subscriptionStart")}</span>
                  <span className="text-ink">{formatUserDateTime(viewingReceipt.subscription_start, userTimezone)}</span>
                </div>
              )}
              {viewingReceipt.subscription_expiration && (
                <div className="flex justify-between">
                  <span className="text-ink-soft">{t("receipt.subscriptionExpiration")}</span>
                  <span className="text-ink">{formatUserDateTime(viewingReceipt.subscription_expiration, userTimezone)}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function ReviewRow({ k, v, active, warn, strong }: { k: string; v: string; active?: boolean; warn?: boolean; strong?: boolean }) {
  const cls = active ? "text-ok" : warn ? "text-warn font-medium" : "text-ink";
  return (
    <div className="flex items-center justify-between">
      <span className="text-ink-soft">{k}</span>
      <span className={`${strong ? "font-semibold capitalize" : ""} ${cls}`}>{v}</span>
    </div>
  );
}

function PlanCard({
  plan,
  currency,
  current,
  onSelect,
}: {
  plan: AvailablePlan;
  currency: string;
  current: boolean;
  onSelect: () => void;
}) {
  const { t } = useLocale();
  const price = getPlanPrice(plan, currency);
  const features = (() => {
    if (!plan.features_json) return [];
    try { return Object.entries(JSON.parse(plan.features_json)).filter(([, v]) => v).map(([k]) => k); } catch { return []; }
  })();

  return (
    <div className={`rounded-lg border p-4 flex flex-col gap-1.5 text-sm ${current ? "border-brand-500/50 bg-brand-tint/30" : "border-line"}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold capitalize text-ink">{plan.name}</span>
        {current && <Badge tone="green">{t("billing.current")}</Badge>}
        {plan.badge && !current && <Badge tone="blue">{plan.badge}</Badge>}
      </div>

      {plan.description && (
        <div className="text-[11px] text-ink-muted">{plan.description}</div>
      )}

      <div className="text-lg font-semibold font-display text-ink">
        {price != null ? (
          <>
            {formatPrice(price, currency)}
            {plan.duration_days ? <span className="text-xs text-ink-muted font-normal"> / {plan.duration_days}d</span> : null}
          </>
        ) : (
          t("billing.custom")
        )}
      </div>

      {features.length > 0 && (
        <div className="text-[10px] text-ink-muted mt-1 space-y-0.5">
          {features.slice(0, 5).map((f) => (
            <div key={f}>&bull; {f.replace(/_/g, " ")}</div>
          ))}
          {features.length > 5 && <div>{t("billing.more", { n: features.length - 5 })}</div>}
        </div>
      )}

      <div className="mt-2">
        <Button
          variant={current ? "secondary" : "primary"}
          size="sm"
          className="w-full"
          disabled={current}
          onClick={onSelect}
        >
          {current ? t("billing.currentPlan") : t("billing.choosePlan")}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dynamic payment instructions — configuration-driven.
//
// Renders ONLY the selected method's owner-defined configuration:
//   - description (method intro)
//   - information blocks (beneficiary, RIB, wallet, ...)
//   - client input fields (rendered by type: text/number/phone/date/datetime/
//     email/image) with per-field validation
//   - receipt upload (required for manual methods unless disabled by owner)
//
// There is NO hardcoded per-method branch: switching Cash Plus → CIH → Wafa →
// Crypto replaces the displayed data because each method carries its own
// config object. Field values are keyed generically, so no stale state leaks
// between methods.
// ---------------------------------------------------------------------------
function DynamicPaymentInstructions({
  session,
  methodName,
  timeLeft,
  fieldValues,
  setFieldValues,
  proofFile,
  setProofFile,
  proofUrl,
  proofUploading,
  proofError,
  onProofFileChange,
  submittingManual,
  onSubmit,
  onBack,
}: {
  session: CheckoutSession;
  methodName: string;
  timeLeft: string;
  fieldValues: Record<string, string>;
  setFieldValues: (v: Record<string, string>) => void;
  proofFile: File | null;
  setProofFile: (f: File | null) => void;
  proofUrl: string;
  proofUploading: boolean;
  proofError: string;
  onProofFileChange: (f: File | null) => void;
  submittingManual: boolean;
  onSubmit: () => void;
  onBack: () => void;
}) {
  const { t } = useLocale();
  const isExpired = timeLeft === "Expired";
  const cfg = session.owner_config;
  const fields = cfg?.client_fields || [];
  const infoBlocks = cfg?.information || [];
  const receiptRequired = cfg?.receipt_required !== false;
  const isCrypto = session.payment_method_type === "manual_crypto";
  const [copied, setCopied] = useState(false);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const setField = (key: string, value: string) => {
    setFieldValues({ ...fieldValues, [key]: value });
  };

  // Per-type validation used by the submit button.
  const fieldError = (f: ClientFieldDef): string | null => {
    const raw = (fieldValues[f.key] || "").trim();
    if (f.required && !raw) return t("checkout.fieldRequired");
    if (!raw) return null;
    if (f.type === "number") {
      if (Number.isNaN(Number(raw))) return t("checkout.fieldInvalidNumber");
      const min = f.validation?.match(/min:(-?[\d.]+)/)?.[1];
      const max = f.validation?.match(/max:(-?[\d.]+)/)?.[1];
      if (min !== undefined && Number(raw) < Number(min)) return t("checkout.fieldMin", { n: min });
      if (max !== undefined && Number(raw) > Number(max)) return t("checkout.fieldMax", { n: max });
    }
    if (f.type === "phone") {
      const digits = raw.replace(/[^\d]/g, "");
      if (digits.length < 8 || digits.length > 15) return t("checkout.fieldInvalidPhone");
    }
    if (f.type === "email") {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(raw)) return t("checkout.fieldInvalidEmail");
    }
    if (f.type === "date" || f.type === "datetime") {
      if (Number.isNaN(new Date(raw).getTime())) return t("checkout.fieldInvalidDate");
    }
    return null;
  };

  const firstError = fields.map(fieldError).find((e) => e !== null) || null;
  const allRequiredFilled = fields.every((f) => !f.required || (fieldValues[f.key] || "").trim());
  const canSubmit = !isExpired && allRequiredFilled && !firstError && (!receiptRequired || !!proofUrl) && !submittingManual;

  return (
    <Card title={isCrypto ? t("checkout.cryptoInstructions") : t("checkout.manualInstructions")} icon="info">
      <div className="flex flex-col gap-4">
        {timeLeft && (
          <div className={`flex items-center justify-between rounded-lg border px-4 py-2.5 ${
            isExpired
              ? "border-danger/30 bg-danger/5"
              : "border-warn/30 bg-warn/5"
          }`}>
            <span className={`text-sm font-semibold ${isExpired ? "text-danger" : "text-warn"}`}>
              {isExpired ? t("checkout.paymentExpired") : t("checkout.timeRemaining")}
            </span>
            <span className={`font-mono text-lg font-bold ${isExpired ? "text-danger" : "text-warn"}`}>
              {timeLeft}
            </span>
          </div>
        )}

        <div className="rounded-lg border border-brand-500/30 bg-brand-tint/20 p-4">
          <div className="flex items-center justify-between mb-1">
            <p className="text-sm font-semibold text-ink">{methodName}</p>
            {isCrypto && session.network && <Badge tone="blue">{session.network}</Badge>}
          </div>

          {/* DESCRIPTION — the method's own intro text */}
          {cfg?.description && (
            <p className="text-xs text-ink-soft mb-3 leading-relaxed">{cfg.description}</p>
          )}
          {!cfg?.description && (
            <p className="text-xs text-ink-muted mb-3">{t("checkout.followInstructions")}</p>
          )}

          {/* Crypto amount + deposit address */}
          {isCrypto && session.expected_amount && session.ticker && (
            <div className="flex items-center justify-between rounded-md bg-input border border-line px-3 py-2 mb-3">
              <div>
                <span className="text-xs text-ink-muted block">{t("checkout.amountToSend")}</span>
                <span className="text-lg font-mono font-bold text-ink">
                  {session.expected_amount} <span className="text-sm font-normal text-ink-muted">{session.ticker}</span>
                </span>
              </div>
              <button
                type="button"
                onClick={() => handleCopy(session.expected_amount!)}
                className="text-xs text-brand-400 hover:text-brand-500 transition-colors"
              >
                {copied ? t("checkout.copied") : t("checkout.copy")}
              </button>
            </div>
          )}
          {isCrypto && session.deposit_address && (
            <div className="rounded-md bg-input border border-line px-3 py-2 mb-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-ink-muted">{t("checkout.depositAddress")}</span>
                <button
                  type="button"
                  onClick={() => handleCopy(session.deposit_address!)}
                  className="text-xs text-brand-400 hover:text-brand-500 transition-colors"
                >
                  {copied ? t("checkout.copied") : t("checkout.copyAddress")}
                </button>
              </div>
              <p className="font-mono text-sm text-ink break-all leading-relaxed bg-background/50 rounded p-2 border border-line/50">
                {session.deposit_address}
              </p>
            </div>
          )}

          {/* Manual reference (generated by the system) */}
          {session.manual_reference && (
            <div className="flex items-center justify-between rounded-md bg-input border border-line px-3 py-2 mb-3">
              <div>
                <span className="text-xs text-ink-muted block">{t("checkout.referenceNumber")}</span>
                <span className="text-sm font-mono font-semibold text-ink">{session.manual_reference}</span>
              </div>
              <button
                type="button"
                onClick={() => handleCopy(session.manual_reference!)}
                className="text-xs text-brand-400 hover:text-brand-500 transition-colors"
              >
                {t("checkout.copy")}
              </button>
            </div>
          )}

          {/* INFORMATION — structured blocks from the owner config */}
          {infoBlocks.length > 0 && (
            <div className="mt-3 space-y-1.5">
              {infoBlocks.map((b, i) => (
                <div key={i} className="flex items-start justify-between rounded-md bg-input border border-line px-3 py-2">
                  <div>
                    <span className="text-xs text-ink-muted block">{b.label}</span>
                    <span className="text-sm font-medium text-ink break-all">{b.value}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleCopy(b.value)}
                    className="text-xs text-brand-400 hover:text-brand-500 transition-colors ml-2"
                  >
                    {copied ? t("checkout.copied") : t("checkout.copy")}
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Legacy instructions fallback (owner_config may be absent for old checkouts) */}
          {infoBlocks.length === 0 && session.manual_instructions && (
            <pre className="mt-3 text-sm text-ink-soft whitespace-pre-wrap font-sans leading-relaxed">
              {session.manual_instructions}
            </pre>
          )}

          {session.expired_at && (
            <div className="mt-3 p-2 rounded bg-warn/10 border border-warn/30 text-xs text-warn">
              {t("checkout.paymentDeadline", { date: new Date(session.expired_at).toLocaleString() })}
            </div>
          )}
        </div>

        {/* CLIENT FIELDS — rendered dynamically from the owner config */}
        {fields.length > 0 && (
          <div className="flex flex-col gap-3">
            {fields.map((f) => (
              <DynamicField
                key={f.key}
                field={f}
                value={fieldValues[f.key] || ""}
                onChange={(v) => setField(f.key, v)}
                error={fieldError(f)}
              />
            ))}
          </div>
        )}

        {/* RECEIPT UPLOAD — required for manual methods unless owner disabled it */}
        {receiptRequired && (
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-ink">{t("checkout.proofOfPayment")} <span className="text-danger">*</span></label>
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.pdf"
              onChange={(e) => onProofFileChange(e.target.files?.[0] || null)}
              className="h-9 px-2 rounded-lg bg-input border border-line text-sm text-ink w-full focus:outline-none focus:ring-2 focus:ring-brand-500/40 file:mr-3 file:rounded-md file:border-0 file:bg-brand-tint file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-brand-400"
            />
            <p className="text-xs text-ink-muted">{t("checkout.acceptedTypes")}</p>
            {proofUploading && <p className="text-xs text-brand-400">{t("checkout.uploadingProof")}</p>}
            {proofUrl && !proofError && <p className="text-xs text-ok">{t("checkout.proofUploaded")}</p>}
            {proofError && <p className="text-xs text-danger">{proofError}</p>}
          </div>
        )}

        <div className="flex gap-2">
          <Button variant="ghost" onClick={onBack}>{t("common.back")}</Button>
          <Button
            onClick={onSubmit}
            disabled={!canSubmit}
            loading={submittingManual}
          >
            {isExpired ? t("checkout.paymentExpired") : t("checkout.submitPayment")}
          </Button>
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// DynamicField — renders one owner-defined client input by its type.
// ---------------------------------------------------------------------------
function DynamicField({
  field,
  value,
  onChange,
  error,
}: {
  field: ClientFieldDef;
  value: string;
  onChange: (v: string) => void;
  error: string | null;
}) {
  const { t } = useLocale();
  const baseCls = "h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink w-full focus:outline-none focus:ring-2 focus:ring-brand-500/40";
  const errCls = error ? " border-danger/50" : "";
  const label = (
    <label className="text-sm font-medium text-ink">
      {field.label} {field.required && <span className="text-danger">*</span>}
    </label>
  );

  let input: React.ReactNode;
  switch (field.type) {
    case "number":
      input = (
        <input
          type="number"
          step="any"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder || undefined}
          className={baseCls + errCls}
        />
      );
      break;
    case "phone":
      input = (
        <input
          type="tel"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder || undefined}
          className={baseCls + errCls}
        />
      );
      break;
    case "date":
      input = (
        <input
          type="date"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={baseCls + errCls}
        />
      );
      break;
    case "datetime":
      input = (
        <input
          type="datetime-local"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={baseCls + errCls}
        />
      );
      break;
    case "email":
      input = (
        <input
          type="email"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder || undefined}
          className={baseCls + errCls}
        />
      );
      break;
    case "image":
    case "file":
      input = (
        <input
          type="file"
          accept=".jpg,.jpeg,.png,.pdf"
          onChange={(e) => onChange(e.target.files?.[0]?.name || "")}
          className={baseCls + errCls + " file:mr-3 file:rounded-md file:border-0 file:bg-brand-tint file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-brand-400"}
        />
      );
      break;
    default:
      input = (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder || undefined}
          className={baseCls + errCls}
        />
      );
  }

  return (
    <div className="flex flex-col gap-1">
      {label}
      {input}
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
