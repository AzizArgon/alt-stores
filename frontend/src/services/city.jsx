import { createContext, useContext, useState } from 'react'
import { CITIES } from '../config/cities'

const CITY_KEY = 'pc_market_city'
const CityContext = createContext(null)

// The chosen city is remembered in the browser. The catalog starts filtering by it in phase B2
export function CityProvider({ children }) {
  const [city, setCityState] = useState(() => {
    const saved = localStorage.getItem(CITY_KEY)
    return CITIES.includes(saved) ? saved : 'all'
  })
  const setCity = (value) => {
    localStorage.setItem(CITY_KEY, value)
    setCityState(value)
  }
  return <CityContext.Provider value={{ city, setCity }}>{children}</CityContext.Provider>
}

export const useCity = () => useContext(CityContext)
