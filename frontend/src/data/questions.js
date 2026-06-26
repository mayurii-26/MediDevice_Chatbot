// Category configuration with subcategories
export const CATEGORIES = [
  {
    id: "PatientMonitoring",
    label: "Patient Monitoring Devices",
    subcategories: [
      "ECG",
      "Defibrillators",
      "Syringe Pump",
      "Infusion Pumps",
      "Ventilators",
      "Air Bed",
      "Fluid Warmers",
    ],
  },
  {
    id: "Cardiology",
    label: "Cardiology",
    subcategories: [
      "ECG Machines",
      "Defibrillators",
      "Stress Test",
      "Ambulatory Blood Pressure (ABPM)",
      "Holter Monitor",
    ],
  },
  {
    id: "Anaesthesia",
    label: "Anaesthesia",
    subcategories: [
      "Laryngoscopes",
      "Resuscitator",
      "Video Laryngoscope",
      "Anaesthesia Workstation",
    ],
  },
  {
    id: "OTComplex",
    label: "OT Complex",
    subcategories: ["Surgery Lights", "OT Tables"],
  },
  {
    id: "MotherChildCare",
    label: "Mother and Child Care",
    subcategories: [
      "Pulse Oximeters",
      "Radiant Warmer",
      "Phototherapy",
      "Bubble CPAP System",
      "Neonatal Ventilator",
    ],
  },
];

// Category-wise suggested questions
export const CATEGORY_QUESTIONS = {
  PatientMonitoring: [
    "What is IntelliVue MX550?",
    "What is IntelliVue MX750?",
    "What is Efficia CM120?",
    "What are the features of IntelliVue MX550?",
    "What are the features of Efficia CM120?",
    "What are the specifications of IntelliVue MX550?",
    "What are the specifications of Efficia CM120?",
    "Compare IntelliVue MX550 and MX750.",
    "Difference between syringe pump and infusion pump?",
    "Compare ventilators and patient monitors.",
  ],
  Cardiology: [
    "What is PageWriter TC50?",
    "Tell me about HeartStart FRx AED.",
    "What is a Holter Monitor?",
    "What are the features of PageWriter TC50?",
    "What are the features of HeartStart FRx AED?",
    "What are the specifications of PageWriter TC50?",
    "What are the specifications of HeartStart FRx AED?",
    "Compare Holter Monitor and ABPM.",
    "Compare PageWriter TC50 and TC70.",
    "Compare ECG machine and stress test system.",
  ],
  Anaesthesia: [
    "What is a Video Laryngoscope?",
    "What is an Anaesthesia Workstation?",
    "What is a Resuscitator?",
    "What are the features of a Video Laryngoscope?",
    "What are the features of an Anaesthesia Workstation?",
    "What are the specifications of an Anaesthesia Workstation?",
    "What are the specifications of a Video Laryngoscope?",
    "Compare Laryngoscope and Video Laryngoscope.",
    "Compare Resuscitator and Ventilator.",
  ],
  OTComplex: [
    "What are Surgery Lights?",
    "What is an OT Table?",
    "What are the features of Surgery Lights?",
    "What are the features of OT Tables?",
    "What are the specifications of Surgery Lights?",
    "What are the specifications of OT Tables?",
    "Compare LED and Halogen Surgery Lights.",
    "Compare different OT Table types.",
  ],
  MotherChildCare: [
    "What is Bubble CPAP System?",
    "What is a Radiant Warmer?",
    "What is Phototherapy?",
    "What are the features of Bubble CPAP System?",
    "What are the features of Neonatal Ventilator?",
    "What are the specifications of Bubble CPAP System?",
    "What are the specifications of Neonatal Ventilator?",
    "Compare Bubble CPAP and Neonatal Ventilator.",
    "Compare Radiant Warmer and Incubator.",
    "Compare different Phototherapy systems.",
  ],
};

// Default questions shown when no category is selected
export const suggestedQuestions = [
  "What is IntelliVue MX550?",
  "What is Efficia CM120?",
  "Tell me about HeartStart FRx AED",
  "What is Avalon CL?",
  "What is PageWriter TC50?",
  "What is a Holter Monitor?",
  "What is Bubble CPAP System?",
  "What is an Anaesthesia Workstation?",
];
