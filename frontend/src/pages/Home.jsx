import "../website.css";
import Hero from "../components/Hero";
import FeaturedProducts from "../components/FeaturedProducts";
import WhyChooseUs from "../components/WhyChooseUs";
import ServicesSection from "../components/ServicesSection";
import StatsSection from "../components/StatsSection";
import Testimonials from "../components/Testimonials";

export default function Home({ onOpenChat }) {
  return (
    <main>
      <Hero onOpenChat={onOpenChat} />
      <FeaturedProducts />
      <StatsSection />
      <WhyChooseUs />
      <ServicesSection />
      <Testimonials />
    </main>
  );
}
